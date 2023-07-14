# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import copy
import logging

import re
from bs4 import BeautifulSoup
import phonenumbers
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from dateutil.relativedelta import relativedelta
import requests
from urllib.parse import urlparse, parse_qs
from benedict import benedict
from datetime import datetime
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.utils.encrypt_utils import encrypt_telekom

logger = logging.getLogger(__name__)

class CreditChecker_SK_4ka(CreditCheckerWeb):
    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "username": { "type" : "string"},
                    "password" : { "type" : "string"},
                },
                "required": ["username", "password"]
            }
        },
        "required": ["phone_number", "credit_checker_params"]
    }

    URL_WEB_INIT = "https://www.4ka.sk/moja-zona/acr"
    URL_WEB_LOGIN = "https://www.4ka.sk/moja-zona/prihlasenie/prihlasenie/redirect" # can also be taken from id=loginForm
    #https://www.4ka.sk/session-management/me
    #https://www.4ka.sk/moja-zona/acr-api/aggregation
    URL_WEB_DASHBOARD = "https://www.4ka.sk/moja-zona/ecare/aktualna-spotreba"
    URL_WEB_PREPAID_USAGE = "https://www.4ka.sk/moja-zona/ecare/api/cost-control/product-residuals/421951707461"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_SK_4ka.CONFIG_SCHEMA_CREDIT)

    def get_phone_number_api(self):
        number = self.get_phone_number()
        x = phonenumbers.parse(number, None)
        number = phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.E164)
        number = number.replace('+','')
        return number
    
    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)
    
    @staticmethod
    def get_auth_value(response):
        res = re.search("<input type=\"hidden\" name=\"auth\" value=\\'(.+?)\\'", response.text)
        auth = res.group(1)
        return auth

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()

        r = self.s.get(CreditChecker_SK_4ka.URL_WEB_INIT)
        auth = CreditChecker_SK_4ka.get_auth_value(r)
        param_login = {
            "auth": auth,
            "userName": "mobileatlas@sba-research.org",
            "password": "MobileAtlas21#"
        }
        r = self.s.post(CreditChecker_SK_4ka.URL_WEB_LOGIN, data=param_login)
        api_header = {'spPrefix': "ECARE_"}
        self.s.headers.update(api_header)
        r = self.s.get(CreditChecker_SK_4ka.URL_WEB_DASHBOARD)

        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                
                r = self.s.get(CreditChecker_SK_4ka.URL_WEB_PREPAID_USAGE.format(self.get_phone_number_api()))
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json
                
                #resp_json("totalResiduals")
                remaining_bytes = 0
                amount = resp_json.get("totalResiduals.DATA.amount")
                unit = resp_json.get("totalResiduals.DATA.unitType")
                if amount and unit:
                    merged = f"{amount} {unit}"
                    remaining_bytes = -convert_size_to_bytes(merged)
                if remaining_bytes:
                    ret.traffic_bytes_total = remaining_bytes
                    ret.bill_dump = r.text
                if ret.traffic_bytes_total is None:
                    raise ValueError("Failed to retrieve current bill")
                else:
                    break
            except Exception:
                if i < retry:
                    self.s = None
                else:
                    raise 
        if new_base:
            # similar to ro_orange 4ka reserve 32mb (8mb in roaming but only reserved when conenction established)
            #ret.traffic_bytes_total -= 32*CreditChecker.MEGABYTE
            ret.traffic_bytes_total -= 8*CreditChecker.MEGABYTE
            self.base_bill = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill)
        self.current_bill = ret
        return ret
