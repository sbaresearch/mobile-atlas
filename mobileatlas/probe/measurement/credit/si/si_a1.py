import copy
import csv
import logging
from queue import Queue
import re
import time
from pytz import timezone
import pytz
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from dateutil.relativedelta import relativedelta
import requests
from benedict import benedict
from datetime import datetime
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.mediator.mm_definitions import ModemManagerSms

logger = logging.getLogger(__name__)



class CreditChecker_SI_A1(CreditCheckerWeb):
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

    TIMEZONE = timezone('Europe/Ljubljana')

    #https://moj.a1.si/ssologin/GetLoginRequest?linkType=login&isMobile=false&returnUrl=%252fpregled%252fmoje-razmerje&_=1647693252880
    URL_WEB_INIT = "https://moj.a1.si/ssologin/GetLoginRequest?linkType=login&isMobile=false"
    URL_WEB_LOGIN = "https://prijava.a1.si/SSO/Login/Login"
    URL_GET_JWT_TOKEN = "https://moj.a1.si/SsoLogin/ReissueToken"
    #https://moj.a1.si/api/usage/detailed?Service=38630799512&SubscriberServiceType=Msisdn&BanNumber=&BenNumber=&OrderBy=Date&SortOrder=desc&ShowAllItems=false&Page=1&PageSize=25&MinDate=&MaxDate=&DirectionList2=&CallTypeList2=Vse+storitve&CalledNumber=&SubscriberType=PostpaidUnbilled&FsisdnNumberList2=&FromDate=&ToDate=&CallType=Vse+storitve&CalledNumber=&_=1647693501975
    URL_WEB_BILL_SUMMARY = "https://moj.a1.si/api/usage/detailed?Service=38630799512"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_SI_A1.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)


    #<form action="/SSO/Login/Login" class="form-horizontal" id="loginForm" method="post"><input name="__RequestVerificationToken" type="hidden" value="2WKFdQPkIYy9xMExP9scBGNWSmeaZXY-tFyLKQS9OIzwya1A9FVgfFYBWP5yWAHpetFccBDF-V5Fo6Bj3nsIYSsmkys1"> 
    @staticmethod
    def get_verification_token(response):
        res = re.search('<input name="__RequestVerificationToken" type="hidden" value="(.+?)" />', response.text)
        verification_token = res.group(1)
        return verification_token

    #<form id="authTicketForm" action="https://moj.a1.si/ssologin?returnUrl=/" method="POST">
    #    <input id="authTicket" name="authTicket" type="hidden" value="80000003rz1eL1TCN3ceh+rFKHiKXyLKnCJ41SuOm1qeG+CsLnoWfIYJCGbnlf+7enWVjAluTs0gIpSDAUJu0MMkLhTHlNbcYg95w10MEh93RmQ/2ki7SnkX95GgfgKux6299/xqvGF737gINjVTf3IjxL2h8gEnhTqSbYHi462uf9SHxEhLo0nz58abyzFwJFFQCEUglCy33tw5qKQ+Xvew25CFPbvSBxxFqwlbrmbzjLzrfMW5De02Q3eq5ekZhx/X8W3bUZOIlX08blucvLObcDOoNSPQnCnwCqTJy+clkuehgtbPTB6eC1/7HDm3wgulS3cKEkcljr3pZjYTvUFv6GRgRY+PEFveRAFXgFJH7uUvUmUVmVSN60BfeIq3BWhfGh30OKxLhcm7gHYG2RI98lqx1g==" />
    #    <input id="subscriberService" name="subscriberService" type="hidden" value="38630799512" />
    #    <input id="isOwner" name="isOwner" type="hidden" value="False" />
    #</form>
    @staticmethod
    def get_hidden_login_form(response):
        url = re.search('<form id="authTicketForm" action="(.+?)"', response.text).group(1)
        params = {
            "authTicket": re.search('<input id="authTicket" name="authTicket" type="hidden" value="(.+?)"', response.text).group(1),
            "subscriberService": re.search('<input id="subscriberService" name="subscriberService" type="hidden" value="(.+?)"', response.text).group(1),
            "isOwner": re.search('<input id="isOwner" name="isOwner" type="hidden" value="(.+?)"', response.text).group(1)
        }
        return url, params

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        
        r = self.s.get(CreditChecker_SI_A1.URL_WEB_INIT)
        resp_json = benedict(r.json())
        login_url = resp_json.get('url')

        r = self.s.get(login_url)
        token = CreditChecker_SI_A1.get_verification_token(r)
        param_login = {
            "__RequestVerificationToken": token,
            "UserName": "mobileatlas",
            "Password": "MobileAtlas21#",
            "IsSamlLogin": "False",
            "InternalBackUrl": "",
            "IsPopUp": "True"
        }
        #headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        r = self.s.post(CreditChecker_SI_A1.URL_WEB_LOGIN, data=param_login)#, headers=headers)

        url, params = CreditChecker_SI_A1.get_hidden_login_form(r)
        r = self.s.post(url, params)
        
        r = self.s.get(CreditChecker_SI_A1.URL_GET_JWT_TOKEN)        
        resp_json = benedict(r.json())
        jwt_token = resp_json.get('token')
        #login_url = resp_json.get('apiurl')
        auth_bearer = {'Authorization': f"Bearer {jwt_token}"}
        self.s.headers.update(auth_bearer)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()    
                
                r = self.s.get(CreditChecker_SI_A1.URL_WEB_BILL_SUMMARY)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json
                info = resp_json.get('Usage', [])
                
                info_data = [x for x in info if x.get('Description') == "Prenos podatkov"]  #get data elem
                info_data = CreditChecker_SI_A1.convert_list(info_data) #convert timestamps and data bytes
                if new_base:
                    self.base_bill_list = info_data
                    
                new_entries = CreditCheckerWeb.subtract_list_of_dict(info_data, self.base_bill_list)
                date_old_entries = self.parser.startup_time - relativedelta(minutes=5)   # discard entries that are from old sessions
                new_entries = [x for x in new_entries if x.get('Date') > date_old_entries]
                if len(info):
                    latest_entry = max(info, key=lambda e: e['Date'])
                    ret.timestamp_effective_date = latest_entry.get("Date", None)
                ret.traffic_bytes_total = sum(map(lambda x: int(x['GprsData']), new_entries))
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
            e["Date"] =  CreditChecker_SI_A1.TIMEZONE.localize(datetime.strptime(e.get("Date"), '%Y-%m-%dT%H:%M:%S')).astimezone(pytz.utc) #CreditChecker.iso8601_to_utc(e.get("Date")) # "2022-03-18T23:37:46"
        return dict_list



#sms_state_changed /org/freedesktop/ModemManager1/SMS/0: 448 (2022-03-18T12:34:44+01:00): Stanje na racunu je: 5.00 EUR. Racun velja do: 16.06.2022. Iz zakupa A1 Simpl mali je na voljo se 498 enot. Enote so veljavne do 17.04.2022. V EU/EEA gostovanju je na voljo se 500.00 MB. A
class CreditChecker_SI_A1_SMS(CreditChecker):
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
            super().__init__(mobile_atlas_mediator, parser, use_sms = True)#, use_ussd=True)
            self.sleep = 60*5 # check credit every 5mins
            self.free_units = Queue()
            self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE

    def sms_received(self, sms: ModemManagerSms):
        try:
            result = re.search('Iz zakupa A1 Simpl mali je na voljo se (.+?) enot', sms.get_text())
            if result:
                units = result.group(1)
                units = f"{units} MB"
                units = convert_size_to_bytes(units)
                self.free_units.put(units)
        except:
            pass

    def receive_free_units(self):
        self.mobile_atlas_mediator.cleanup() #clean any present sms and calls
        self.free_units = Queue()
        a = self.mobile_atlas_mediator.send_ussd_code(code="*448#")
        return self.free_units.get(timeout=120)

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                received_units = self.receive_free_units()
                ret.traffic_bytes_total = received_units * -1

                if ret.traffic_bytes_total is None:
                    raise ValueError("Failed to retrieve current bill")
                else:
                    break
            except Exception:
                if i < retry:
                    time.sleep(60*12) # since sms can only be requested once every 10 mins?
                else:
                    raise 
        if new_base:
            self.base_bill = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill)
        self.current_bill = ret
        return ret
