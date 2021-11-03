import copy
import logging
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from dateutil.relativedelta import relativedelta
from pytz import timezone
import pytz
import requests
from datetime import datetime
from benedict import benedict
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator

logger = logging.getLogger(__name__)

class CreditChecker_AT_Drei(CreditCheckerWeb):
    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "phone_number" : {"type" : "string"},
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "password" : { "type" : "string"},
                },
                "required": ["password"]
            }
        },
        "required": ["phone_number", "credit_checker_params"]
    }

    URL_LOGIN = 'https://www.drei.at/de/login/'
    URL_APP_JSON = 'https://www.drei.at/selfcare/restricted/jsonCoCoInfo'
    TIMEZONE = timezone('Europe/Vienna')
    
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_AT_Drei.CONFIG_SCHEMA_CREDIT)

    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        # login
        r = self.s.get(CreditChecker_AT_Drei.URL_LOGIN)
        param = {
            'retUrl':'',
            'username': self.get_phone_number(),
            'password': self.get_password(),
            'stayLoggedIn': 'true'
        }
        r = self.s.post(CreditChecker_AT_Drei.URL_LOGIN, param)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                r = self.s.get(CreditChecker_AT_Drei.URL_APP_JSON)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json
                resp_json = resp_json.get('JsonCoCoResponse', {})
                effective_date = resp_json.get('cocoResponse.billingEffectiveDate', None)
                effective_date = datetime.strptime(effective_date, '%Y-%m-%d %H:%M:%S.%f UTC').astimezone(pytz.utc)
                #ret.timestamp_effective_date = effective_date

                avail_units = resp_json.get('cocoResponse.groups', [])
                data_units = [x for x in avail_units if x.get('displayName') == "Daten"]  #get data elements

                bytes_total = 0
                for x in data_units:
                    val = x.get('consumedAmount', 0)
                    unit = x.get('unit', '')
                    if all([unit, val]):
                        consumed_bytes = convert_size_to_bytes(f'{val} {unit}')
                        bytes_total += consumed_bytes
                ret.traffic_bytes_total = bytes_total
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