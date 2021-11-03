import copy
import logging
from queue import Queue
import re
from dateutil.relativedelta import relativedelta
import requests
from benedict import benedict
from datetime import datetime
from decimal import Decimal
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.mediator.mm_definitions import ModemManagerSms

logger = logging.getLogger(__name__)

class CreditChecker_AT_HoT(CreditCheckerWeb):
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

    URL_LOGIN = "https://www.hot.at/login/"
    URL_LOGIN_PUK = "https://www.hot.at/api/?Mode=Selfcare&Function=LoginPuk"
    #{
    #	"Msisdn": "067762990392",
    #	"Puk": "12234567"
    #}

    URL_LOGIN_REQUEST_TAN = "https://www.hot.at/api/?Mode=Selfcare&Function=sendLoginPin"

    URL_LOGIN_SUBMIT_TAN = "https://www.hot.at/api/?Mode=Selfcare&Function=checkLoginPin"
    #{
    #	"Pin": "1234"
    #}

    URL_BILL_DATA = "https://www.hot.at/api/?Mode=Selfcare&Function=getHeaderBox"
    #EGN as pdf via https://www.hot.at/selfcare/zahlungen.html#calls
    
    #UTC_OFFSET = relativedelta(hours=-2)
    
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.get_phone_number = parser.get_phone_number
        self.s = None
        self.tan_queue = Queue()
        if self.use_sms_tan():
            self.use_sms = True
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_AT_HoT.CONFIG_SCHEMA_CREDIT)

    def get_puk(self):
        return self.parser.get_config().get('credit_checker_params.puk', None)

    def use_sms_tan(self):
        return self.get_puk() == None

    def get_csrf_token(self, response):
        #headers: { "CSRFToken": "BbXrFUYKcKURdOzG42U5075184" }
        csrf_token = re.search('headers: { "CSRFToken": "(.+?)" }', response.text).group(1)
        return csrf_token

    def sms_received(self, sms: ModemManagerSms):
        #Lieber Kunde, Ihr Einmal-Code für das Login auf mein HoT lautet 104139. Ihr HoT Service Team
        try:
            tan = re.search('Login auf mein HoT lautet (.+?)\. Ihr HoT Service Team', sms.get_text()).group(1).strip(" \n\r")
            self.tan_queue.put(tan)
        except:
            pass

    def receive_sms_tan(self):
        self.tan_queue = Queue()  #clear old items from queue
        param = {"Msisdn": self.get_phone_number()}
        r = self.s.post(CreditChecker_AT_HoT.URL_LOGIN_REQUEST_TAN, param)
        return self.tan_queue.get(timeout=60)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()

        r = self.s.get(CreditChecker_AT_HoT.URL_LOGIN)
        csrf_token = self.get_csrf_token(r)
        self.s.headers.update({'CSRFToken': csrf_token})

        if self.use_sms_tan():
            tan = self.receive_sms_tan()
            param = {"Pin": tan}
            r = self.s.post(CreditChecker_AT_HoT.URL_LOGIN_SUBMIT_TAN, param)
        else:
            param = {
                "Msisdn": self.get_phone_number(),
                "Puk": self.get_puk()
            }
            r = self.s.post(CreditChecker_AT_HoT.URL_LOGIN_PUK, param)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                r = self.s.get(CreditChecker_AT_HoT.URL_BILL_DATA)
                resp_json = r.json()
                ret.bill_dump = resp_json
                resp_json = benedict(resp_json)
                info = resp_json.get('Result.ConnectionsSummary', {})
                ret.traffic_bytes_total = info.get('Data.Sum', None)
                if ret.traffic_bytes_total:
                    ret.traffic_bytes_total = Decimal(ret.traffic_bytes_total) * CreditChecker.MEGABYTE
                ret.credit_consumed_credit = info.get('Total.Price', None)
                if ret.credit_consumed_credit:
                    ret.credit_consumed_credit = Decimal(ret.credit_consumed_credit.replace(",", "."))
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