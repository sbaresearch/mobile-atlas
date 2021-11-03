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

class CreditChecker_HR_Telekom(CreditCheckerWeb):
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

    # for working code for login via homepage, see https://gitlab.sba-research.org/ggegenhuber/mobile-atlas/-/blob/4a1f8d98f2ee490dc605a06a2f4727233ce29e30/hr_telekom.py

    # https://cms-cdn.yo-digital.com/cdn/TEFsPbNQPa1nfcu1nazud2wUv7g8GBV1/18.9.10/config.json
    #https://t-app.hrvatskitelekom.hr/customerBills/unpaid/summary/
    #https://t-app.hrvatskitelekom.hr/profiles/
    #https://t-app.hrvatskitelekom.hr/profiles/?sub=ca09f496-31be-4144-aae0-294cffd05385&magentaEnabled=false&hybridEnabled=true&scEnabled=false&loyaltyEnabled=false&subscriptionServiceEnabled=false&genCenToken=true&deviceId=916860b4-f39e-4304-adf6-1083458460c0&devicesWithEMI=false

    #https://t-app.hrvatskitelekom.hr/dashboard/product/385996826485/?enableFreeUnit=true&showUnlimited=true&priority=primary&serviceOutageEnabled=false
    #https://t-app.hrvatskitelekom.hr/manageServices/product/385996826485/details/?enableFreeUnit=true&transferUnitsEnabled=true&prepaidBalanceDetails=true&serviceOutageEnabled=false&devicesWithEMI=false&enableVasCategories=false
    #https://t-app.hrvatskitelekom.hr/manageServices/product/385996826485/addons?planEnabled=true&customCategory=false&enableAdvancedAddon=true

    URL_APP_LOGIN = "https://t-app.hrvatskitelekom.hr/login/"
    APP_PUBLIC_KEY = "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDMmKReuzuaCk10Wa6vv4ybcqjVN3cruj27IRp9YhdgEw9jcG728Aj9s60mY8B/czzW5ntKJQktyBRBZ98BKznRWBrVN/n9JR/m1UDc38PW4BPe4z5VtBe99dyFcJQ1VJij6HG0BFtw3isPR5NAUAAyGnXpNWKCat5TtBckqVatBQIDAQAB"
    APP_HEADER = {
        'Authorization': '2640cb08-44a6-11e8-842f-0ed5f89f718b', 
        'X-Client-Version': '15.12.1 (13149) @ 2013149-55b09dba93 (15.12.1)'
    }
    URL_APP_DASHBOARD = "https://t-app.hrvatskitelekom.hr/dashboard/product/{}/?enableFreeUnit=true&showUnlimited=true&priority=primary&serviceOutageEnabled=false" #less precise because it summarizes all services
    URL_APP_BILL = "https://t-app.hrvatskitelekom.hr/manageServices/product/{}/details/?enableFreeUnit=true&transferUnitsEnabled=true&prepaidBalanceDetails=true&serviceOutageEnabled=false&devicesWithEMI=false&enableVasCategories=false"
 

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 2 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_HR_Telekom.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)
    
    def get_phone_number_api(self):
        number = self.get_phone_number()
        x = phonenumbers.parse(number, None)
        number = phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.E164)
        number = number.replace('+','')
        return number

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        self.s.headers.update(CreditChecker_HR_Telekom.APP_HEADER)
        # login via web
        param = {
            "telekomLogin": {
                "password": encrypt_telekom(CreditChecker_HR_Telekom.APP_PUBLIC_KEY, self.get_password()),
                "username": self.get_username()
            },
            "type": "telekom"
        }
        r = self.s.post(CreditChecker_HR_Telekom.URL_APP_LOGIN, json=param)
        access_token = r.json().get('accessToken', None)
        auth_bearer = {'Authorization': f"Bearer {access_token}"}
        self.s.headers.update(auth_bearer)
        logger.info("credit_checker loggedin")


    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                url = CreditChecker_HR_Telekom.URL_APP_BILL.format(self.get_phone_number_api())
                r = self.s.get(url)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json

                units = resp_json.get('consumptionGroups', [])
                units_data = [x for x in units if x.get('type') == "data"]  #get data elem
                units_data = units_data[0].get('consumptions', [])

                converted_entries = []
                for x in units_data:
                    x = benedict(x)
                    val = x.get('remaining.value', 0)
                    unit = x.get('remaining.unit', '')
                    avail_bytes = convert_size_to_bytes(f'{val} {unit}')
                    
                    timestamp = x.get('updatedTime', None)
                    timestamp = CreditChecker.iso8601_to_utc(timestamp, msecs=True)
                    converted_entries.append({'bytes': avail_bytes, 'time' : timestamp})

                if converted_entries:
                    total_bytes_remaining = sum(e['bytes'] for e in converted_entries)
                    timestamp = min(e['time'] for e in converted_entries)
                    ret.traffic_bytes_total = total_bytes_remaining * -1
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
            self.base_bill = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill)
        self.current_bill = ret
        return ret