


import json
import logging
import re
from datetime import datetime
from dateutil.relativedelta import relativedelta
from queue import Queue
from benedict import benedict
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.mediator.mm_definitions import ModemManagerSms

logger = logging.getLogger(__name__)

class CreditChecker_AT_eety(CreditCheckerWeb):
    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "phone_number" : {"type" : "string"},
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "puk" : { "type" : "string"},
                }
            }
        },
        "required": ["phone_number"]
    }
    
    URL_LOGIN = "https://selfcare.eety.at/de/customer/login"
    URL_LOGIN_PUK = "https://selfcare.eety.at/de/customer/login/puk"
    #{
    #    "identifier": "4366565432590",
    #    "route": "/de/customer/login/puk",
    #    "token": "36622476"
    #}

    URL_LOGIN_REQUEST_TAN = "https://selfcare.eety.at/de/customer/login/send-code"
    # {"identifier": "4366565432590"}

    URL_LOGIN_SUBMIT_TAN = "https://selfcare.eety.at/de/customer/login/code"
    #{
    #    "identifier": "4366565432590",
    #    "route": "/de/customer/login/code",
    #    "token": "12345"
    #}

    URL_LOGIN_RETRIEVE_USER = "https://selfcare.eety.at/customer/dashboard/"

    URL_BILL = "https://selfcare.eety.at/customer/timeline/"
    #original params:
    #{
    #    "count": 100,
    #    "endpointId": 151421,
    #    "eventTypes": "",
    #    "filtered": 100,
    #    "fromDate": "2021-07-01",
    #    "length": 20,
    #    "orderDir": "desc",
    #    "start": 0,
    #    "toDate": "2021-07-08",
    #    "userId": 151433
    #}
    #however this two params are enough to get some info back:
    #{
    #    "endpointId": 151421,
    #    "userId": 151433
    #}

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.get_phone_number = parser.get_phone_number
        self.s = None
        self.user = benedict()
        self.tan_queue = Queue()
        if self.use_sms_tan():
            self.use_sms = True
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_AT_eety.CONFIG_SCHEMA_CREDIT)

    def get_puk(self):
        return self.parser.get_config().get('credit_checker_params.puk', None)

    def use_sms_tan(self):
        return self.get_puk() == None

    def sms_received(self, sms: ModemManagerSms):
        #Sehr geehrter eety Kunde. Dein Selfcare Login-Token lautet: 30987953.
        try:
            tan = re.search('Dein Selfcare Login-Token lautet: (.+?)\.', sms.get_text()).group(1).strip(" \n\r")
            self.tan_queue.put(tan)
        except:
            pass

    def receive_sms_tan(self):
        self.tan_queue = Queue()  #clear old items from queue
        param = {"identifier": self.get_phone_number()}
        r = self.s.post(CreditChecker_AT_eety.URL_LOGIN_REQUEST_TAN, param)
        return self.tan_queue.get(timeout=60)

    def get_csrf_token(self, response):
        #headers: { "X-CSRF-TOKEN": "eEHXi7YilxUu6pp0wys40rIWZgD9mwa5MwtfGbPRRus" }
        csrf_token = re.search('<meta name="csrf-token" content="(.+?)" />', response.text).group(1)
        return csrf_token

    def get_user_object(self, response):
        user = re.search('window.user = ((.|\s)+?);', response.text).group(1)
        user = user.replace("\'", "\"") # replace ' with "
        return benedict(json.loads(user))
    
    def get_user_id(self):
        return self.user.get('user.id', None)
    
    def get_endpoint_id(self):
        return self.user.get('user.accounts[0].endpoints[0].id', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()

        r = self.s.get(CreditChecker_AT_eety.URL_LOGIN)
        csrf_token = self.get_csrf_token(r)
        self.s.headers.update({'X-CSRF-TOKEN': csrf_token})
        self.s.headers.update({'X-Requested-With': 'XMLHttpRequest'})

        login_url = CreditChecker_AT_eety.URL_LOGIN_SUBMIT_TAN if self.use_sms_tan() else CreditChecker_AT_eety.URL_LOGIN_PUK
        token = self.get_puk() or self.receive_sms_tan()

        self.s.headers.update({'X-AUTH-SELF-CARE': 'true'})
        param = {
            "identifier": self.get_phone_number(),
            "token": token
        }
        r = self.s.post(login_url, param)
        r = self.s.get(CreditChecker_AT_eety.URL_LOGIN_RETRIEVE_USER)
        self.user = self.get_user_object(r)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                param = {
                    "userId": self.get_user_id(),
                    "endpointId": self.get_endpoint_id()
                }
                r = self.s.post(CreditChecker_AT_eety.URL_BILL, param)
                resp_json = r.json()
                ret.bill_dump = resp_json
                resp_json = benedict(resp_json)

                info = resp_json.get('events', [])
                info = CreditChecker_AT_eety.convert_list(info) #convert timestamps

                if new_base:
                    self.base_bill = info
                new_entries = CreditCheckerWeb.subtract_list_of_dict(info, self.base_bill)

                new_entries = [x for x in new_entries if x.get('eventSubType') == "DATA"]
                date_old_entries = self.parser.startup_time - relativedelta(minutes=5)   # discard entries that are from old sessions
                new_entries = [x for x in new_entries if x.get('startTimestamp') > date_old_entries]

                if len(info):
                    latest_entry = max(info, key=lambda e: e['startTimestamp'])
                    ret.timestamp_effective_date = latest_entry.get("startTimestamp", None)
                ret.traffic_bytes_total = sum(map(lambda x: int(x['totalConsumedUnitCount']), new_entries))
                ret.traffic_cnt_connections = len(new_entries)
                if ret.traffic_bytes_total is None:
                    raise ValueError("Failed to retrieve current bill")
                else:
                    break
            except Exception:
                if i < retry:
                    self.s = None
                else:
                    raise 
        self.current_bill = ret
        return ret


    @staticmethod
    def convert_list(dict_list):
        for e in dict_list:
            e["startTimestamp"] = CreditChecker.iso8601_to_utc(e.get("startTimestamp")) #datetime.strptime(e.get("startTimestamp"), '%Y-%m-%dT%H:%M:%S%z').astimezone(timezone.utc).replace(tzinfo=None)            
        return dict_list
