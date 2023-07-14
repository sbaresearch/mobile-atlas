# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import copy
import logging
import re

from bs4 import BeautifulSoup
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from dateutil.relativedelta import relativedelta
import requests
import phonenumbers
from benedict import benedict
from datetime import datetime
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator

logger = logging.getLogger(__name__)

class CreditChecker_RO_Orange(CreditCheckerWeb):
    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "username": { "type" : "string"},
                    "password" : { "type" : "string"},
                },
                "required": ["password"]
            }
        },
        "required": ["phone_number", "credit_checker_params"]
    }

    HEADER_APP_AUTH = {"Authorization": "Basic MTI0ZDkwNTMtMmIwMy00ODEwLTg2NmQtNDA0MTE4YzRjZjI5OjdJa2I5WExRQ3FRdVppS0RjY0ROTE1LcTJhZjcxdkNDeGZBZg=="}
    URL_APP_LOGIN = "https://www.orange.ro/accounts/token"

    URL_APP_BILL_SUMMARY = "https://www.orange.ro/myaccount/api/v4/{}/cronos" #alternatively there is also "https://www.orange.ro/myaccount/api/v4/cronos/79530236"

    #connectionwise bill needs ages to update..., see "Detaliile de convorbiri pentru luna curenta sunt afisate cu o intarziere de 72 de ore si au caracter informativ."
    URL_APP_BILL_CONNECTIONWISE = "https://www.orange.ro/myaccount/api/v4/callsDetailsByPeriod/0746387842?offset=0&count=1000&sort=CALL_DATE_TIME&order=DESC&withCost=false&groupResults=true&from=18-06-2021&to=18-07-2021"
    #duration contains transmitted bytes, e.g. this is ~5mb: {"callDateTime":"18/07/2021 17:57","description":"","duration":"5542666","dialedDigits":"net","cost":"0.27","callingDeviceId":"0746387842","callingDevice":"0746387842","resourceType":"date","credit":"4.73"}


    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_RO_Orange.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', self.get_phone_number_api())  #phone number works as well at login
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)
    
    def get_phone_number_api(self):
        number = self.get_phone_number()
        x = phonenumbers.parse(number, None)
        number = phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.NATIONAL)
        number = number.replace(' ','')
        return number

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        self.s.headers.update(CreditChecker_RO_Orange.HEADER_APP_AUTH)
        param = {
            "grant_type":"password",
            "scope":"oauth.userinfo.extended myaccountb2c.access asyncchat.read",
            "username": self.get_username(),
            "password": self.get_password(),
            "access_type":"offline"
        }
        r = self.s.post(CreditChecker_RO_Orange.URL_APP_LOGIN, json=param)
        access_token = r.json().get('access_token', None)
        auth_bearer = {'Authorization': f"Bearer {access_token}"}
        self.s.headers.update(auth_bearer)
        logger.info("credit_checker loggedin")

    def get_bill_connectionwise(self):
        ref = {"Referer": "https://www.orange.ro/myaccount/reshape/invoice-cronos/cronos"}
        self.s.headers.update(ref)
        r = self.s.get(CreditChecker_RO_Orange.URL_APP_BILL_CONNECTIONWISE)
        return r.json()

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()

                r = self.s.get(CreditChecker_RO_Orange.URL_APP_BILL_SUMMARY.format(self.get_phone_number_api()))
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json


                timestamp = resp_json.get('lastRefreshDate')    #"2021-07-27T22:06:47+03",
                timestamp = CreditChecker.iso8601_to_utc(timestamp+':00')

                units = resp_json.get('resources', [])
                units_data = [x for x in units if x.get('marketingCategory') == "Date"]
                
                # national data is decreased in roaming as well, if we keep both roaming and national data in the list the used data will get counted twice
                units_data = [x for x in units_data if x.get('name') == "internet national"]

                remaining_bytes = 0
                for x in units_data:
                    #val = x.get('consumed', 0) # consumed is always 0.0 but remaining gets reduced
                    val = x.get('remaining', 0)
                    unit = x.get('resourceUnit', '')
                    remaining_bytes += convert_size_to_bytes(f'{val} {unit}')

                ret.traffic_bytes_total = remaining_bytes * -1
                ret.timestamp_effective_date = timestamp
                
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
            # when the SIM connects to a base station the available data is reduced by 10 MB
            # when the SIM connects to a network the 10 MB are added again
            # after cutting the connection the data is instantly credited
            # hotfix to ignore the 10 MB reserve
            # in roaming case (at least in AT) the operator only reserves 2,5mb
            # we should probably find a way to disable rf at startup...
            ret.traffic_bytes_total -= 10*CreditChecker.MEGABYTE
            #ret.traffic_bytes_total -= 2.5*CreditChecker.MEGABYTE
            
            self.base_bill = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill)
        self.current_bill = ret
        return ret
