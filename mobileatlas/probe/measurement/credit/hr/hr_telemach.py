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
from mobileatlas.probe.measurement.utils.encrypt_utils import encrypt_telekom

logger = logging.getLogger(__name__)

class CreditChecker_HR_Telemach(CreditCheckerWeb):
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
    
    
    URL_WEB_INIT = "https://telemach.hr/account/signin"
    URL_WEB_LOGIN = "https://telemach.hr/gateway/userauthAPI/1.0/scauth/userauth/auth"
    HTTP_AUTH_USER = "webscuser"
    HTTP_AUTH_PASS = "k4md93!k334f3"

    URL_WEB_BILL = "https://telemach.hr/gateway/scAPI/1.0/selfcareapi/THR/number/{}/resource/{}"
    #https://telemach.hr/gateway/scAPI/1.0/selfcareapi/THR/customer/1bbf4ba3ea9b3f26/customer
    #https://telemach.hr/gateway/scAPI/1.0/selfcareapi/THR/user/1bbf4ba3ea9b3f26/profile
    #https://telemach.hr/gateway/scAPI/1.0/selfcareapi/THR/number/2793be248ee4e853/resource/00385957129292
 

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
        self.identity = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_HR_Telemach.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)
    
    def get_identity(self):
        return self.identity
    
    def get_phone_number_api(self):
        number = self.get_phone_number()
        x = phonenumbers.parse(number, None)
        number = phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.E164)
        number = number.replace('+','00')
        return number

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        r = self.s.get(CreditChecker_HR_Telemach.URL_WEB_INIT)
        # login via web
        param = {
            "username" : self.get_username(),
            "password" : self.get_password(), #"U2FsdGVkX1/QG1XTdY/zyeNWQZ3hN8YOoX3nNgxpuDk=",
            "grantType" : "password",
            "domainId" : "THR",
            "applicationId" : "lol"
        }
        self.s.auth = (CreditChecker_HR_Telemach.HTTP_AUTH_USER, CreditChecker_HR_Telemach.HTTP_AUTH_PASS)
        r = self.s.post(CreditChecker_HR_Telemach.URL_WEB_LOGIN, json=param)
        resp_json = benedict(r.json())
        self.identity = resp_json.get('UserAuth.identity')
        access_header = {'accessToken': resp_json.get('UserAuth.accessToken')}
        self.s.headers.update(access_header)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                url = CreditChecker_HR_Telemach.URL_WEB_BILL.format(self.get_identity(), self.get_phone_number_api())
                r = self.s.get(url)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json

                units = resp_json.get('Resources.MobileResourceUnit', [])
                units_data = [x for x in units if x.get('type') == "DATA"]  #get data elem
                #units_data = units_data[0].get('consumptions', [])

                total_bytes_remaining = 0
                for x in units_data:
                    x = benedict(x)
                    val = x.get('remaining', 0)
                    unit = x.get('unit', '')
                    total_bytes_remaining += convert_size_to_bytes(f'{val} {unit}')
                
                if total_bytes_remaining:
                    ret.traffic_bytes_total = total_bytes_remaining * -1

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
            self.base_bill = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill)
        self.current_bill = ret
        return ret