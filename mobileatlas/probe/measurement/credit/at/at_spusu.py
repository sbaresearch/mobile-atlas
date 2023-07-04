# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

from queue import Queue
from decimal import Decimal
import logging
import time

from mobileatlas.probe.measurement.mediator.mm_definitions import ModemManagerSms
from bs4 import BeautifulSoup
from datetime import datetime
from dateutil.relativedelta import relativedelta
import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Hash import SHA
from urllib.parse import quote
import base64
import re
import json
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from traceback import format_exc

logger = logging.getLogger(__name__)

class CreditChecker_AT_spusu(CreditCheckerWeb):
    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "phone_number" : {"type" : "string"},
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "password" : { "type" : "string"},
                },
            }
        },
        "required": ["phone_number"]
    }

    URL_LOGIN = "https://www.spusu.at/login"
    URL_BILL = "https://www.spusu.at/egn/"
    NO_DATA = "Für die ausgewählte Rufnummer sind in diesem Monat keine Daten vorhanden"
    UTC_OFFSET = relativedelta(hours=-2)

    DEFAULT_PUBKEY = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4sDROi419u4RrPNGzbQcM2dHI+YV7CImcv/ncRklx9/VdHyKn7OiecKbxd7ItPE8jxXM/Xezis0GaSHxkEabqSPbCxobFBc89ZFkkxravfn/KfnaqTI8REVLrMOfENILut5Vw6hg/YS4PspRf9cSCsW6MEa90nBmlMIkTB2UVojYVWO6YSJgpnlSE7sVRjeViFJX/s90942tV3UkP+Sx1RT/ZTCh/uD8NLl/ad4N/9TPU5y2TyRo/0+cHJKZ8LhT34O5IxrOyvpDQrQ3lzlV4+W630+4u8U8gqNd0KgV4gQovN5Y0EUNqViarfl75COlGn+yj2u4ak7L9hRbB2FnfwIDAQAB"
    
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.connectionwise_billing_available = True
        self.get_phone_number = parser.get_phone_number
        self.s = None
        self.key = None
        self.tan_queue = Queue()
        if self.use_sms_tan():
            self.use_sms = True
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_AT_spusu.CONFIG_SCHEMA_CREDIT)

    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def use_sms_tan(self):
        return self.get_password() == None

    def encrypt_spusu(self, pwdTan):
        message = pwdTan.encode('utf-8')
        public_key = RSA.importKey(base64.b64decode(self.key))
        cipher = PKCS1_v1_5.new(public_key)
        #encrypted_message = public_key.encrypt(pw.encode('utf8'), random_phrase)[0]
        encrypted_message = cipher.encrypt(message)
        base64_message = base64.b64encode(encrypted_message)
        urlencoded = quote(base64_message, safe='')
        return urlencoded

    def sms_received(self, sms: ModemManagerSms):
        #"Hier ist Ihr TAN Code f\u00fcr den Login auf Mein spusu: SAX\nMit freundlichen Gr\u00fc\u00dfen, Ihr spusu Team"
        try:
            tan = re.search('Login auf Mein spusu: (.+?)\n', sms.get_text()).group(1).strip(" \n\r")
            self.tan_queue.put(tan)
        except:
            pass

    def receive_sms_tan(self):
        self.tan_queue = Queue()  #clear old items from queue
        param = {
            "action": [
                "SendTan",
                ""
            ],
            "pwdTan": "",
            "username": self.get_phone_number()
        }
        r = self.s.post(CreditChecker_AT_spusu.URL_LOGIN, param)
        return self.tan_queue.get(timeout=60)

   
    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        r = self.s.get(CreditChecker_AT_spusu.URL_LOGIN)
        soup = BeautifulSoup(r.content, "html.parser")
        self.key = soup.find(id="encryptionPublicKey").get("value", CreditChecker_AT_spusu.DEFAULT_PUBKEY)
        pwdTan = self.get_password() or self.receive_sms_tan()
        pwdTan = self.encrypt_spusu(pwdTan)
        param = {
            "action": [
                "Login",
                ""
            ],
            "pwdTan": pwdTan,
            "username": self.get_phone_number()
        }
        r = self.s.post(CreditChecker_AT_spusu.URL_LOGIN, param)
        logger.info("credit_checker should be logged into customer selfcare!")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        logger.info("_retrieve_current_bill...")
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                today = datetime.today()
                monthyear = datetime(today.year, today.month, 1) - relativedelta(months=1)
                monthyear = datetime.strftime(monthyear, "%Y%m")
                param = {
                    "monthyear": monthyear,
                    #"showCall": "on",
                    #"showSMS": "on",
                    "showData": "on",
                }
                resp = self.s.post(CreditChecker_AT_spusu.URL_BILL, data=param)
                if CreditChecker_AT_spusu.NO_DATA not in resp.text:
                    columnConfig = re.search('var columnConfig = (.+?)\n', resp.text).group(1).strip(" ;\n\r")
                    columnConfig = json.loads(columnConfig)
                    rowData = re.search('var rowData = (.+?)\n', resp.text).group(1).strip(" ;\n\r")
                    rowData = json.loads(rowData)
                    info = CreditChecker_AT_spusu.create_list(columnConfig, rowData[:-1])    # skip last element (which is sum)
                else:
                    info = []   # no data available
                if new_base:
                    self.base_bill = info
                new_entries = CreditCheckerWeb.subtract_list_of_dict(info, self.base_bill)
                date_old_entries = self.parser.startup_time - relativedelta(minutes=5)   # discard entries that are from old sessions
                new_entries = [x for x in new_entries if x.get('Datum') > date_old_entries]
                if len(info):
                    latest_entry = max(info, key=lambda e: e['Datum'])
                    ret.timestamp_effective_date = latest_entry.get("Datum", None)
                ret.traffic_bytes_downstream = sum(map(lambda x: int(x['Daten (empfangen)']), new_entries))
                ret.traffic_bytes_upstream = sum(map(lambda x: int(x['Daten (gesendet)']), new_entries))
                ret.credit_consumed_credit = sum(map(lambda x: int(x["Kosten (netto)"]), new_entries))
                ret.traffic_bytes_total = ret.traffic_bytes_downstream + ret.traffic_bytes_upstream
                ret.traffic_cnt_connections = len(new_entries)
                ret.bill_dump = {
                    "new_entries": new_entries,
                    "full_dump" : info
                }
                break
            except requests.exceptions.ConnectionError:
                #urllib3.exceptions.ProtocolError: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
                #requests.exceptions.ConnectionError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
                print("ConnectionError")
                pass
            except AttributeError:
                print(resp.text)
            except Exception:
                logger.error(f"exception: {format_exc()}")
                if i < retry:
                    self.s = None
                    time.sleep(self.get_sleep())
                else:
                    raise ValueError("Failed to retrieve current bill")
        self.current_bill = ret
        return ret

    @staticmethod
    def create_list(columnConfig, rowData):
        ret = []
        for r in rowData:
            new_row = {}
            for i, c in  enumerate(columnConfig):
                colName = c.get('title')
                new_row[colName] = r[i]
            ret.append(new_row)
        return CreditChecker_AT_spusu.convert_list(ret)

    @staticmethod
    def convert_list(dict_list):
        for e in dict_list:
            e["Datum"] = datetime.strptime(e.get("Datum"), '%d.%m.%Y&nbsp;%H:%M') + CreditChecker_AT_spusu.UTC_OFFSET
            e["Kosten (netto)"] = Decimal(e.get("Kosten (netto)").strip(" €").replace(",",'.'))
            e["Daten (empfangen)"] = convert_size_to_bytes(e.get("Daten (empfangen)"), decimal_separator=",")
            e["Daten (gesendet)"] = convert_size_to_bytes(e.get("Daten (gesendet)"), decimal_separator=",")
        return dict_list