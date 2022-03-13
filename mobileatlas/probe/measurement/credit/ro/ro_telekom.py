import copy
import logging
import re
import time

from bs4 import BeautifulSoup
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from dateutil.relativedelta import relativedelta
import requests
import phonenumbers
from queue import Queue
from benedict import benedict
from datetime import datetime
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.utils.encrypt_utils import encrypt_telekom

logger = logging.getLogger(__name__)

class CreditChecker_RO_Telekom_Ussd(CreditChecker): #CreditChecker_RO_Telekom_Ussd
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser, use_ussd = True)
        self.unit_queue = Queue()

    def ussd_notification_received(self, message):
        try:
            #Optiunea N5 este activa pana 12Sep2021 . Pana atunci mai ai 4228 MB trafic de date la viteza 4G.
            result = re.search('Optiunea N5 este activa pana 12Sep2021 \. Pana atunci mai ai (.+?) (.+?) trafic de date la viteza 4G\.', message)
            if result:
                used = result.group(1)
                unit = result.group(2)
                val = f"{used} {unit}"
                used_bytes = convert_size_to_bytes(val)
                self.unit_queue.put(used_bytes)
        except:
            pass

    def receive_free_units(self):
        self.unit_queue = Queue()
        a = self.mobile_atlas_mediator.send_ussd_code(code="*123*2#")
        return self.unit_queue.get(timeout=60)

     # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                free_units = self.receive_free_units()
                ret.traffic_bytes_total = -free_units
                ret.bill_dump = {'free_bytes': free_units}

                if ret.traffic_bytes_total is None:
                    raise ValueError("Failed to retrieve current bill")
                else:
                    break
            except Exception:
                if i < retry:
                    time.sleep(60) # since sms can only be requested once every 10 mins?
                else:
                    raise 
        if new_base:
            self.base_bill = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill)
        self.current_bill = ret
        return ret

class CreditChecker_RO_Telekom(CreditCheckerWeb):
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

    URL_APP_LOGIN = "https://oneapp-bff-prd.mobile.telekom.ro/login/"
    APP_PUBLIC_KEY = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqBOkGTrVU1LSkNDBJgl8r1HIKD+LQVxbMGu4WNIVHCSL00MQeQD4DwWXShopj80GQAuJVAyWlWNUVqEn2LIkRQsdmP84EKUe2kYVzsR2dtoAuLLG4T3ek9vKYcqJw6WQRpkSj9MYX1cUeNFs1o6ZVXh/XJPIZX4P9ht5uP60TNK+2dFvTqS1dZphwKrKdm0iXTdvWCv7haDKSjDYwT/Z5ycQl5ubuIgMtciItTkxlZJ5calpP1rtoQRnuinmGMlGPoxPCWeFLnwx/TW9khcJWAn60jil2YaU7ic1ymFDnnuUPcguCsj7GaWwRzTA0YT5PJRlUc9TAgS4qytfN4ZJ6QIDAQAB"

    URL_APP_DASHBOARD = "https://oneapp-bff-prd.mobile.telekom.ro/dashboard/product/{}/?enableFreeUnit=true&showUnlimited=true&priority=primary" #less precise because it summarizes all services
    URL_APP_BILL = "https://oneapp-bff-prd.mobile.telekom.ro/manageServices/product/{}/details/?enableFreeUnit=true&transferUnitsEnabled=false&prepaidBalanceDetails=true"
    #URL_APP_BILL_SUMMARY_ = "https://oneapp-bff-prd.mobile.telekom.ro/customers/"
    #URL_APP_BILL_SUMMARY_ = "https://oneapp-bff-prd.mobile.telekom.ro/manageServices/product/0765927543/usages/" 
    #URL_APP_BILL_SUMMARY_ = "https://oneapp-bff-prd.mobile.telekom.ro/customerBills/unpaid/summary/"


    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 10 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_RO_Telekom.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
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
        param = {
            "telekomLogin": {
                "password": encrypt_telekom(CreditChecker_RO_Telekom.APP_PUBLIC_KEY, self.get_password()),
                "username": self.get_username()
            },
            "type": "telekom"
        }
        r = self.s.post(CreditChecker_RO_Telekom.URL_APP_LOGIN, json=param)
        access_token = r.json().get('accessToken', None)
        auth_bearer = {'Authorization': f"Bearer {access_token}"}
        self.s.headers.update(auth_bearer)
        logger.info("credit_checker loggedin")

    
    def fix_mb_rounding(self, value):
        value = value * 1000 / 1024 #fix because provided MB has conversion error
        value = CreditChecker.round_to_unit(value, 10*CreditChecker.MEGABYTE)
        return value

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                url = CreditChecker_RO_Telekom.URL_APP_BILL.format(self.get_phone_number_api())
                param_bill = {"campaignParameters":{"appDb":{"services":[{"id":self.get_phone_number_api()}]}}}
                r = self.s.post(url, json=param_bill)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json

                units = resp_json.get('consumptionGroups', [])
                units_data = [x for x in units if x.get('type') == "data"]  #get data elem
                units_data = units_data[0].get('consumptions', [])

                converted_entries = []
                for x in units_data:
                    x = benedict(x)
                    val = x.get('used.value', 0)
                    unit = x.get('used.unit', '')
                    used_bytes = convert_size_to_bytes(f'{val} {unit}')
                    #val = x.get('remaining.value', 0)
                    #unit = x.get('remaining.unit', '')
                    #available_bytes = convert_size_to_bytes(f'{val} {unit}')

                    #i think this was fixed by telekom :)
                    #if val and unit == 'MB':
                    #    available_bytes = self.fix_mb_rounding(available_bytes)
                    
                    timestamp = x.get('updatedTime', None)
                    timestamp = CreditChecker.iso8601_to_utc(timestamp, msecs=True)
                    converted_entries.append({'bytes': used_bytes, 'time' : timestamp})

                if converted_entries:
                    total_bytes = sum(e['bytes'] for e in converted_entries)
                    timestamp = min(e['time'] for e in converted_entries)
                    ret.traffic_bytes_total = total_bytes
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
