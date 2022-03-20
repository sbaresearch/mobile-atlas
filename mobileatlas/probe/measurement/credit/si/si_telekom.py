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

class CreditChecker_SI_Telekom(CreditCheckerWeb):
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

    URL_WEB_INIT = "https://moj.telekom.si/sl/Profile/Login"
    URL_WEB_LOGIN_IFRAME = "https://prijava.telekom.si/sso/UI/Login?realm=telekom&service=AuthChain&goto=https%3a%2f%2fmoj.telekom.si%2fsuccess.html&gotoOnFail=https%3a%2f%2fmoj.telekom.si%2fsuccess.html%3ffail%3dtrue"
    URL_WEB_LOGIN = "https://prijava.telekom.si/sso/UI/Login?realm=telekom&amp;service=AuthChain&amp;goto=https%3a%2f%2fmoj.telekom.si%2fsuccess.html&amp;gotoOnFail=https%3a%2f%2fmoj.telekom.si%2fsuccess.html%3ffail%3dtrue"
    #URL_WEB_DASHBOARD = "https://moj.telekom.si/sl/MobileDashboard/Dashboard/Index/041278283"
    URL_WEB_PREPAID_USAGE = "https://moj.telekom.si/sl/MobileDashboard/MobileReadonly/PrepaidUsage/{}" #"https://moj.telekom.si/sl/MobileDashboard/MobileReadonly/PrepaidUsage/041278283"
    URL_WEB_PREPAID_BALANCE = "https://moj.telekom.si/sl/MobileDashboard/MobileReadonly/PrepaidBalance/{}"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_SI_Telekom.CONFIG_SCHEMA_CREDIT)

    def get_phone_number_api(self):
        number = self.get_phone_number()
        x = phonenumbers.parse(number, None)
        number = phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.NATIONAL)
        number = number.replace(' ','')
        return number
    
    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        r = self.s.get(CreditChecker_SI_Telekom.URL_WEB_INIT)
        r = self.s.get(CreditChecker_SI_Telekom.URL_WEB_LOGIN_IFRAME)
        param_login = {
            "IDToken1": self.get_username(),
            "IDToken2": self.get_password(),
            "loginRemember": "on"
        }
        r = self.s.post(CreditChecker_SI_Telekom.URL_WEB_LOGIN, data=param_login)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                
                r = self.s.get(CreditChecker_SI_Telekom.URL_WEB_PREPAID_BALANCE)
                remaining_bytes = 0
                soup = BeautifulSoup(r.content, "html.parser")
                div = soup.find_all('div', {'class' : 'price-big'})
                for d in div:
                    amount = soup.find('span', {'class' : 'ts-m-26'}) 
                    unit = soup.find('span', {'class' : 'grey'}) 
                    merged = f"{amount.text.strip()} {unit.text.strip()}"
                    if 'MB' in merged:
                        remaining_bytes -= convert_size_to_bytes(merged)
                if remaining_bytes:
                    ret.traffic_bytes_total = remaining_bytes
                    ret.bill_dump = r.content
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