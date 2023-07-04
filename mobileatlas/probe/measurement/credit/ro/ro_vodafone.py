# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import copy
import logging
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from queue import Queue
import re
from dateutil.relativedelta import relativedelta
import requests
import phonenumbers
import pytz
from pytz import timezone
from urllib.parse import urlparse, parse_qs
from benedict import benedict
from datetime import datetime
from decimal import Decimal
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.mediator.mm_definitions import ModemManagerSms

logger = logging.getLogger(__name__)

class CreditChecker_RO_Vodafone(CreditCheckerWeb):
    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "phone_number" : {"type" : "string"},
            "credit_checker_params" : {
                "type" : "object",
            }
        },
        "required": ["phone_number"]
    }

    URL_APP_AUTH_INIT = "https://authprime.vodafone.ro/dxl-aws-sso/mvaLogin?seamless=true"  #seamless=true means login via tan-sms; since normal login requires captcha this is our only choice :X

    #URL_BILL_DATA = "https://auth.vodafone.ro/sso/api-gateway/offers/prepaid/current/"
    URL_BILL_DATA = "https://auth.vodafone.ro/sso/api-gateway/subscriber/cost-control/"
    
    TIMEZONE = timezone('Europe/Bucharest')
        
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser, use_sms = True)
        self.get_phone_number = parser.get_phone_number
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.s = None
        self.access_token = None
        self.access_token_timestamp = None
        self.refresh_token = None
        self.tan_queue = Queue()
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_RO_Vodafone.CONFIG_SCHEMA_CREDIT)

    def sms_received(self, sms: ModemManagerSms):
        #Codul tău unic este:199164 - IMPORTANT: nu-ti vom cere niciodata acest cod prin apel telefonic sau in scris. Codul unic e doar pentru tine si iti permite accesul in contul tau My Vodafone – nu il comunica altor persoane.
        try:
            tan = re.search('Codul tău unic este:(.+?) - IMPORTANT', sms.get_text()).group(1).strip(" \n\r")
            self.tan_queue.put(tan)
        except:
            pass

    def get_phone_number_api(self):
        number = self.get_phone_number()
        x = phonenumbers.parse(number, None)
        number = phonenumbers.format_number(x, phonenumbers.PhoneNumberFormat.E164)
        number = number.replace('+','')
        return number

    def set_access_token(self, token_response):
        self.access_token = token_response.get('accessToken', None)
        self.refresh_token = token_response.get('refreshToken', None)
        auth = {'React_cookie': f"Authorization={self.access_token}"}
        self.s.headers.update(auth)
        self.access_token_valid_until = datetime.now(pytz.utc) + relativedelta(minutes=50)  #token is valid for 60min --> refresh after 50min

    def refresh_token(self):
        param = {
            "accessToken": self.access_token,
            "refreshToken": self.refresh_token
        }
        r = self.post("https://authprime.vodafone.ro/dxl-aws-sso/api-gateway-proxy/refresh", json=param)
        self.set_access_token(r.json())

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()

        # at first initiate session for sending sms pin
        r = self.s.get(CreditChecker_RO_Vodafone.URL_APP_AUTH_INIT)
        url = r.url.replace('/authorize#', '/web-apis/authorize') #bypass javascript check
        r = self.s.get(url)

        # then request sms pin
        self.mobile_atlas_mediator.cleanup() #clean any present sms and calls
        resp_json = benedict(r.json())
        next_request = resp_json.get('links.urn:vodafoneid:userkeyWizard')
        self.s.headers.update(next_request.get('headers')) #set csrf token
        url = next_request.get('href')

        self.tan_queue = Queue() # clear queue (since there could be old elements)
        param = {
            "rememberMe": "true",
            "userkeyType": "MSISDN",
            "userkeyValue": self.get_phone_number_api()
        }
        r = self.s.post(url, json=param)

        pin = self.tan_queue.get(timeout=240) #wait 2mins, beacuse 'Unfortunately, you cannot generate a new PIN for 2 minute(s), you have reached the limit of attempts.'

        # then send the pin to the server 
        resp_json = benedict(r.json())
        next_request = resp_json.get('links.urn:vodafoneid:identify')
        self.s.headers.update(next_request.get('headers')) #set csrf token
        url = next_request.get('href')
        param = {
            "pinCode":pin
        }
        r = self.s.post(url, json=param)

        # then get the session token
        resp_json = benedict(r.json())
        next_request = resp_json.get('links.urn:vodafoneid:follow')
        url = next_request.get('href')
        r = self.s.get(url)
        parsed_url = urlparse(r.url)
        param = parse_qs(parsed_url.query)
        param = {k: v[0] for k, v in param.items()}
        r = self.s.post("https://auth.vodafone.ro/sso/api-gateway/obtaintoken/", param)

        # and activate session token
        self.set_access_token(r.json())
        url = f"https://auth.vodafone.ro/sso/api-gateway/seamless/{self.get_phone_number_api()}"
        r = self.s.get(url)

        logger.info("credit_checker loggedin")
        #self.use_sms = False

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                if self.access_token_valid_until < datetime.now(pytz.utc):
                    self.refresh_token()

                r = self.s.get(CreditChecker_RO_Vodafone.URL_BILL_DATA)
                resp_json = benedict(r.json())
                ret.bill_dump = resp_json

                effective_date = resp_json.get('transactionSuccess.lastUpdateDate')
                effective_date = datetime.fromtimestamp(effective_date/1000)
                effective_date = CreditChecker_RO_Vodafone.TIMEZONE.localize(effective_date).astimezone(pytz.utc)
                #effective date seems to be just current timestamp but sadly does not mean that all bills until that timestamp had been processed >.<
                #ret.timestamp_effective_date = effective_date

                units = resp_json.get('transactionSuccess.currentExtraoptions.extendedBalanceList', []) #alternatively extendedBalanceList
                units_data = [x for x in units if x.get('amountTypeId') == "data"]    # filter for data units
                units_data = [x for x in units_data if x.get('amountUnit') != "unl"]  # remove unlimited data
                total_bytes_remaining = 0
                for x in units_data:
                    val = x.get('remainingAmount')
                    unit = x.get('amountUnit')
                    if all([unit, val]):
                        bytes_remaining = convert_size_to_bytes(f"{val} {unit}")
                        total_bytes_remaining += bytes_remaining
                ret.traffic_bytes_total = total_bytes_remaining * -1

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