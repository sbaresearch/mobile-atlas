# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import copy
from decimal import Decimal
import logging

import pytz
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
import requests
from datetime import datetime, timedelta
from pytz import timezone
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator

logger = logging.getLogger(__name__)

class CreditChecker_AT_yesss(CreditCheckerWeb):
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

    URL_LOGIN = "https://www.yesss.at/kontomanager.at/index.php"
    URL_BILL_DATA = "https://www.yesss.at/kontomanager.at/datentransfers.php"

    NO_DATA = "enthält derzeit keine Einträge."

    TIMEZONE = timezone('Europe/Vienna')

    
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser, use_internet_gw = True)
        self.connectionwise_billing_available = True
        self.get_phone_number = parser.get_phone_number
        self.base_bill = []
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_AT_yesss.CONFIG_SCHEMA_CREDIT)

    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        # login
        r = self.s.get(CreditChecker_AT_yesss.URL_LOGIN)
        param = {
            "login_rufnummer": self.get_phone_number(),
            "login_passwort": self.get_password(),
            "login_button": ""
        }
        r = self.s.post(CreditChecker_AT_yesss.URL_LOGIN, param)
        logger.info("credit_checker loggedin")

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()

                r = self.s.get(CreditChecker_AT_yesss.URL_BILL_DATA)
                soup = BeautifulSoup(r.content, "html.parser")
                info = []
                if CreditChecker_AT_yesss.NO_DATA not in r.text:
                    htmltable = soup.find('div', { 'class' : 'min-768 table-group' })
                    table_body = htmltable.find('tbody')
                    rows = table_body.find_all('tr')
                    for row in rows:
                        new_entry = {}
                        cols = row.find_all('td')
                        for col in cols:
                            attr = col.get('data-title', None)
                            if attr:
                                val = col.text.strip()
                                new_entry[attr] = val
                        info.append(new_entry)

                if new_base:
                    self.base_bill = info
                info = CreditChecker_AT_yesss.convert_list(info)
                new_entries = CreditCheckerWeb.subtract_list_of_dict(info, self.base_bill)
                date_old_entries = self.parser.startup_time - relativedelta(minutes=5)   # discard entries that are from old sessions
                new_entries = [x for x in new_entries if x.get("Datum/Uhrzeit:") > date_old_entries]

                if len(info):
                    latest_entry = max(info, key=lambda e: e["Datum/Uhrzeit:"])
                    ret.timestamp_effective_date = latest_entry.get("Datum/Uhrzeit:", None)
                ret.traffic_bytes_downstream = sum(map(lambda x: int(x["Download:"]), new_entries))
                ret.traffic_bytes_upstream = sum(map(lambda x: int(x["Upload:"]), new_entries))
                ret.credit_consumed_credit = sum(map(lambda x: int(x["Kosten (EUR):"]), new_entries))
                ret.traffic_bytes_total = ret.traffic_bytes_downstream + ret.traffic_bytes_upstream
                ret.traffic_cnt_connections = len(new_entries)
                ret.bill_dump = {
                    "new_entries": new_entries,
                    "full_dump" : info
                }
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
        #[{'Datum/Uhrzeit:': '18.06.2021 12:54:24', 'Dauer:': 'k. A.*', 'Upload:': '3\xa0KB', 'Download:': '9\xa0KB', 'Land:': 'Österreich', 'Kosten (EUR):': '0,000'}]
        for e in dict_list:
            e["Datum/Uhrzeit:"] = CreditChecker_AT_yesss.TIMEZONE.localize(datetime.strptime(e.get("Datum/Uhrzeit:"), '%d.%m.%Y %H:%M:%S')).astimezone(pytz.utc)
            e["Upload:"] = convert_size_to_bytes(e.get("Upload:").replace("\n", ""), decimal_separator=",")
            e["Download:"] = convert_size_to_bytes(e.get("Download:").replace("\n", ""), decimal_separator=",")
            e["Kosten (EUR):"] = Decimal(e.get("Kosten (EUR):").replace(",",'.'))
        return dict_list