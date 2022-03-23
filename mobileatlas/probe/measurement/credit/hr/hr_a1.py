import copy
import logging
import re

from bs4 import BeautifulSoup
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

logger = logging.getLogger(__name__)

class CreditChecker_HR_A1(CreditCheckerWeb):
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

    #URL_APP_LOGIN = "https://webauth.a1.hr/mcrm_digest/api/v3/login"
    URL_INIT = "https://moj.a1.hr"
    URL_LOGIN = "https://webauth.a1.hr/vasmpauth/ProcessLoginServlet"   #lold: alternatively just visiting any api link and use http auth also works :X

    #https://secure.a1.hr/mcrm_oauth/api/v5.91/dashboard/unitsStatusInfo
    #https://secure.a1.hr/mcrm_oauth/api/v5.91/additionalUserInfo
    #https://secure.a1.hr/mcrm_oauth/api/v5.91/bills
    #https://secure.a1.hr/mcrm_oauth/api/v5.91/convertUnits
    #https://secure.a1.hr/mcrm_oauth/api/v5.91/profile

    URL_APP_BILL = "https://secure.a1.hr/mcrm_oauth/api/dashboard?apiVersion=v6.2" #"https://secure.a1.hr/mcrm_oauth/api/v5.91/dashboard"
    URL_WEB_BILL = "https://moj.a1.hr/prepaid/home"
 

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_HR_A1.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        # login via web
        r = self.s.get(CreditChecker_HR_A1.URL_INIT)
        param = {
            "UserID": self.get_username(),
            "Password": self.get_password(),
            "userRequestURL": "https://moj.a1.hr",
            #"serviceRegistrationURL": "",
            #"level": "30",
            #"SetMsisdn": "true",
            #"service": "",
            #"hashpassword": "123"
        }
        r = self.s.post(CreditChecker_HR_A1.URL_LOGIN, param)
        logger.info("credit_checker loggedin")


    def selfcare_web_to_dict(self, response):
        soup = BeautifulSoup(response.content, "html.parser")
        units = soup.find_all('p', {'class' : 'mv-meterTitle'})
        ret = {}
        for u in units:
            k = str(u.next).strip() # str() cause it is a navigablestring
            v = u.next.next.text.strip()
            ret[k] = v
        return ret

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                r = self.s.get(CreditChecker_HR_A1.URL_APP_BILL)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json
                #ret.bill_dump[CreditChecker_HR_A1.URL_APP_BILL] = resp_json 
                #r = self.s.get(CreditChecker_HR_A1.URL_WEB_BILL)
                #ret.bill_dump[CreditChecker_HR_A1.URL_WEB_BILL] = r.content
                #unit_dict = self.selfcare_web_to_dict(r) 

                component_list = resp_json.get('components', [])
                # get summary:
                units = [x for x in component_list if x.get('componentType') == "unitsStatus"]
                units = benedict(units[0])
                disclaimer_time = units.get('disclaimer')
                """ 
                #this code works but is not very precise, better iterate through unitCards and summarize units
                units = units.get('units', [])
                units_data = [x for x in units if x.get('subtitle') == "Interneta"]
                units_data = benedict(units_data[0])
                units_data = units_data.get('title')
                avail_bytes = convert_size_to_bytes(units_data)
                """
                avail_bytes = 0
                # get cards:
                units = [x for x in component_list if x.get('componentType') == "unitCard"]
                for x in units:
                    title = x.get('title')
                    amount = x.get('formattedAmount')
                    if 'NON STOP SOCIAL' not in title: # filter out zero-rating units
                        if 'MB' in amount or 'GB' in amount: # filter out minutes an
                            avail_bytes += convert_size_to_bytes(amount)

                ret.traffic_bytes_total = avail_bytes * -1 

                """ 
                #code for web
                avail_bytes = 0
                #usually web dict is more precise:
                for k, v in unit_dict.items():
                    if 'NON STOP SOCIAL' not in k: # filter out zero-rating units
                        if 'MB' in v or 'GB' in v: # filter out minutes an
                            avail_bytes += convert_size_to_bytes(v)
                ret.traffic_bytes_total = avail_bytes * -1
                """

                #Podaci su posljednji put ažurirani 23.07.2021. u 16:14 sati.
                match = re.search('Podaci su posljednji put ažurirani (.+?)\. u (.+?) sati\.', disclaimer_time)
                date_str = match.group(1)
                time_str = match.group(2)
                date_str = f"{date_str} {time_str}"
                effective_date = datetime.strptime(date_str, '%d.%m.%Y %H:%M').astimezone(pytz.utc)
                ret.timestamp_effective_date = effective_date
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
