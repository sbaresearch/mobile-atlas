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

class CreditChecker_SK_Orange(CreditCheckerWeb):
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

    URL_START = "https://www.orange.sk/prihlasenie/oauth/authorize?response_type=code&client_id=ecare2_prod&scope=user%20openid&state=%2F&acr_values=sk:orange:sso:role:orangeUser"
    URL_LOGIN = "https://www.orange.sk/prihlasenie/oauth/authorize"
    URL_LOGIN_GET_ACCESS_TOKEN = "https://ec2.ocp.orange.sk/ec2-api-monica/userData?code={}"
    URL_BILL_LIST = "https://ec2.ocp.orange.sk/ec2-api-elizabeth/consumption/detail/list"


    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_SK_Orange.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        self.s = requests.Session()
        r = self.s.get(CreditChecker_SK_Orange.URL_START)
        auth = re.search('<input type="hidden" name="auth" value=\'(.+?)\'/>', r.text).group(1)
        param = {
            "auth": auth,
            "reset": "",
            "userName": self.get_username(),
            "password": self.get_password(),
            "remember": "true"
        }
        r = self.s.post(CreditChecker_SK_Orange.URL_LOGIN, param)
        # extract params from forwarded url
        o = urlparse(r.url)
        param = parse_qs(o.query)
        param = {k: v[0] for k, v in param.items()}
        r = self.s.get(CreditChecker_SK_Orange.URL_LOGIN_GET_ACCESS_TOKEN.format(param.get('code')))

        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                r = self.s.get(CreditChecker_SK_Orange.URL_BILL_LIST)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json

                info = resp_json.get('list', [])
                info = CreditChecker_SK_Orange.convert_list(info) #convert timestamps
                info_data = [x for x in info if x.get('consumptionType') == "DATA"]  #get data elem
                if new_base:
                    self.base_bill_list = info
                    
                new_entries = CreditCheckerWeb.subtract_list_of_dict(info_data, self.base_bill_list)
                date_old_entries = self.parser.startup_time - relativedelta(minutes=5)   # discard entries that are from old sessions
                new_entries = [x for x in new_entries if x.get('date') > date_old_entries]
                if len(info):
                    latest_entry = max(info, key=lambda e: e['date'])
                    ret.timestamp_effective_date = latest_entry.get("date", None)
                #ret.credit_consumed_credit = sum(map(lambda x: int(x["price"]), new_entries))
                ret.traffic_bytes_total = sum(map(lambda x: int(x['value']), new_entries))
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
            e["date"] = CreditChecker.iso8601_to_utc(e.get("date"))
        return dict_list