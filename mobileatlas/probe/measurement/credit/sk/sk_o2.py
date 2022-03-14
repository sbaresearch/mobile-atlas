import copy
import logging

import re
from bs4 import BeautifulSoup
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

class CreditChecker_SK_O2(CreditCheckerWeb): #CreditChecker_SK_O2_App
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

    URL_APP_INIT = "https://api.o2.sk/oauth2/authorize?response_type=code&client_id=mnh7xPlMzImonBdnV_JzbK093vYa&redirect_uri=mojeo2sk%3A%2F%2Fcallback%2F&prompt=login&login_hint=%7B%22disable_sso%22%3A%22true%22%7D&scope=PRODUCTION&code_challenge=ZHfvXXr50JQd0v6h3LIN5v0kGXOYqnpYkvT8tw6IWyM&code_challenge_method=S256"
    URL_APP_LOGIN = "https://api.o2.sk/commonauth"
    URL_APP_TOKEN = "https://api.o2.sk/oauth2/token"
    URL_APP_BILL = "https://api.o2.sk/api/subscriberComplex/2.0.0?widget=false"
    #https://api.o2.sk/version
    #https://api.o2.sk/api/me/2.0.0
    #https://api.o2.sk/api/bonus/mcc/1.0.0
    #https://api.o2.sk/api/extra/codes/1.0.0
    #https://api.o2.sk/api/extra/offers/1.0.0
    #https://api.o2.sk/api/registeredCards/1.0.0
    #https://api.o2.sk/api/changeTariffAndMigrationOptions/1.0.0?tariffId=O4%3APRP%3ATARIF%3AVOLNOST


    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_SK_O2.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        r = self.s.get(CreditChecker_SK_O2.URL_APP_INIT)
        
        # extract params from forwarded url
        o = urlparse(r.url)
        param = parse_qs(o.query)
        param = {k: v[0] for k, v in param.items()}
        # login via web
        param_login = {
            "sessionDataKey" : param.get('sessionDataKey'),
            "handler": "UIDAuthenticationHandler",
            "username": self.get_username(),
            "password": self.get_password(),
            "captcha" : ""
        }
        try:
            r = self.s.post(CreditChecker_SK_O2.URL_APP_LOGIN, param_login)
        except requests.exceptions.InvalidSchema as err:
            exception_str = str(err)
            print(exception_str)
            #code = re.search("'mojeo2sk:\/\/callback/?code=(.+?)'", exception_str).group(1)
            code = re.search("code=(.+?)'", exception_str).group(1) # silly but works :X
            print(code)
        app_header = {
            "Authorization": "Basic bW5oN3hQbE16SW1vbkJkblZfSnpiSzA5M3ZZYTpYVjdNa09QOTJmaFNTN0UyU1k0RVpnZ1R6Q1Vh",
            "User-Agent" : "sk.o2.mojeo2/v6.15.2(vc44838)/Android"
        }
        token_params = {
            "code" : code,
            "redirect_uri" : "mojeo2sk://callback/",
            "scope" : "PRODUCTION",
            "grant_type" : "authorization_code",
            "code_verifier" : "YbDuCv7Za1vStbtNtehaI6fpbS4mBG2AzghKcEueRbX1tbNR38hr8p8ksvtQrBm5yuAsQ8Yi1aB4CgDlx8HFdg"
        }
        self.s.headers.update(app_header)
        r = self.s.post("https://api.o2.sk/oauth2/token", token_params)
        access_token = r.json().get('access_token', None)
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
                    
                r = self.s.get(CreditChecker_SK_O2.URL_APP_BILL)
                #resp_json = r.content.replace(b"allowedModification.v2", b"allowedModification_v2")
                resp_json = benedict(r.json(), keypath_separator = '/')
                
                ret.bill_dump = resp_json

                last_update = resp_json.get('subscriberComplex/servicesAndUsage/usageAt') #resp_json.get('subscriberComplex.servicesAndUsage.usageAt')
                last_update = CreditChecker.iso8601_to_utc(last_update, msecs=True)
                
                units = resp_json.get('subscriberComplex/servicesAndUsage/service') #resp_json.get('subscriberComplex.servicesAndUsage.service', [])
                units_data = [x for x in units if x.get('type') == "DATA_ONLYUSED"]  #get data elem
                units_data = [x for x in units_data if x.get('productId') == "TIB:VIRTUAL:GLOB_DATA_NAT"]  #data package is listed several times, only get it once
                units_data = units_data[0].get('fuAllowanceUsage', [])
                units_data = [x for x in units_data if x.get('type') == "DATA_ONLYUSED"]
                
                #"utilizedFU": 2.02,
                #"utilizedFUUnit": "MB",
                #"remainingFU": 497.98,
                #"remainingFUUnit": "MB",
                #"utilizedEUFU": 1.02,
                #"utilizedEUFUUnit": "MB",
                #"remainingEUFU": 498.98,
                #"remainingEUFUUnit": "MB",

                used_bytes = 0
                for x in units_data:
                    x = benedict(x)
                    val = x.get('utilizedFU', 0)
                    unit = x.get('utilizedFUUnit', '')
                    used_bytes += convert_size_to_bytes(f'{val} {unit}')
            
                if used_bytes:
                    ret.traffic_bytes_total = used_bytes
                
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
    
    @staticmethod
    def convert_list(dict_list):
        for e in dict_list:
            e["eventTime"] = CreditChecker.iso8601_to_utc(e.get("eventTime"))
            e["duration"] =  convert_size_to_bytes(e.get("duration") + " MB", decimal_separator=",")
        return dict_list





class CreditChecker_SK_O2_Web(CreditCheckerWeb):
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

    #POST https://api.o2.sk/commonauth
    #sessionDataKey=1001cbf6-0852-4bc0-a8a6-29f73748ec3a&handler=UIDAuthenticationHandler&username=mobileatlas%40sba-research.org&password=MobileAtlas21%23&honeyChange=changethis&honeyoff=&honey=&captcha=umFEj

    URL_BILL = "https://www.o2.sk/moje-o2/spotreba/moje-hovory"
    URL_LOGIN = "https://api.o2.sk/commonauth"

    URL_BILL_JSON = 'https://www.o2.sk/moje-o2/spotreba/moje-hovory?p_p_id=consumptioncalllist_WAR_consumptionportlets&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view&p_p_resource_id=callList&p_p_cacheability=cacheLevelPage&p_p_col_id=column-1&p_p_col_pos=1&p_p_col_count=2'


    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_SK_O2.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        r = self.s.get(CreditChecker_SK_O2.URL_BILL)
        # extract params from forwarded url
        o = urlparse(r.url)
        param = parse_qs(o.query)
        param = {k: v[0] for k, v in param.items()}
        # login via web
        param = {
            "sessionDataKey": param.get('sessionDataKey'), #'85cfae17-3557-4dca-9c61-51389eeaeb38'
            "handler": "UIDAuthenticationHandler",
            "username": self.get_username(),
            "password": self.get_password(),
            "honeyChange": "changethis",
            "honeyoff": "",
            "honey": "",
            "captcha": "umFEj"
        }
        r = self.s.post(CreditChecker_SK_O2.URL_LOGIN, param)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()    
                today = datetime.today()
                yesterday = today - relativedelta(days=1)
                tomorrow = today + relativedelta(days=1)
                param_bill_json = {
                    "eventTimeFrom": datetime.strftime(yesterday, "%Y-%m-%d"),
                    "eventTimeTo": datetime.strftime(tomorrow, "%Y-%m-%d")
                }
                r = self.s.post(CreditChecker_SK_O2.URL_BILL_JSON, json=param_bill_json)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json

                info = resp_json.get('list', [])
                info_data = [x for x in info if "Prenos dát" in x.get('eventTypeDescription')]  #get data elem
                info_data = CreditChecker_SK_O2.convert_list(info) #convert timestamps and data bytes
                if new_base:
                    self.base_bill = info_data
                    
                new_entries = CreditCheckerWeb.subtract_list_of_dict(info_data, self.base_bill)
                date_old_entries = self.parser.startup_time - relativedelta(minutes=5)   # discard entries that are from old sessions
                new_entries = [x for x in new_entries if x.get('eventTime') > date_old_entries]
                if len(info):
                    latest_entry = max(info, key=lambda e: e['eventTime'])
                    ret.timestamp_effective_date = latest_entry.get("eventTime", None)
                ret.traffic_bytes_total = sum(map(lambda x: int(x['duration']), new_entries))
                ret.traffic_cnt_connections = len(new_entries)
                ret.bill_dump = {
                    "new_entries": new_entries,
                    "full_dump" : info
                }
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
    
    @staticmethod
    def convert_list(dict_list):
        for e in dict_list:
            e["eventTime"] = CreditChecker.iso8601_to_utc(e.get("eventTime"))
            e["duration"] =  convert_size_to_bytes(e.get("duration") + " MB", decimal_separator=",")
        return dict_list
