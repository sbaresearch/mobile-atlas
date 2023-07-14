# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

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

# https://www.a1.net/wertkarte-guthaben-abfragen
# https://www.a1.net/hilfe-kontakt/article/Vertrag-Services/Mein-A1/Online-Rechnung-Kosten-Freieinheiten/Wie-kann-ich-Kosten-und-Freieinheiten-meines-mobilen-Produktes-abrufen-/500000000007312/500000000027361
# Schicken Sie ein leeres SMS an 421, um Ihre aktuellen Kosten und Ihr verbrauchtes Datenvolumen abzufragen.
# SMS/7: 0664690421 (2021-07-21T19:09:44+02:00): Lieber A1 Kunde, Ihre Verbindungsentgelte seit Abschluss Ihrer letzten Rechnung betragen ca. EUR 0.00 brutto. Angaben sind ohne Gewähr. Ihr A1 Service Team
# SMS/8: 0664690421 (2021-07-21T19:09:44+02:00): Lieber A1 Kunde, Sie haben seit Abschluss Ihrer letzten Rechnung ca. 15.79 MB Datenvolumen verbraucht. Angaben sind ohne Gewähr. Ihr A1 Service Team
# --> precise but does not updated very often... :-|

# Schicken Sie ein leeres SMS an 411, um Ihre verbrauchten Freieinheiten abzufragen.
# SMS/3: 0664690411 (2021-07-21T19:03:48+02:00): Lieber A1 Kunde, seit Abschluss Ihrer letzten Rechnung haben Sie 0/unlimitiert Freiminuten Ö & EU+, 0/unlimitiert SMS Ö & EU+, 0/unlimitiert MMS Ö & EU+,
# SMS/4: 0664690411 (2021-07-21T19:03:48+02:00): 0,36/unlimitiert MB A1 Free Stream NATIONAL, 0/10 GB A1 Free Stream EU, 0,01/9 GB Daten Ö & EU+ verbraucht.
# SMS/5: 0664690411 (2021-07-21T19:03:49+02:00): Alle Details finden Sie unter www.A1.net/freieinheiten. Ihr A1 Team
# --> seems to be the same as web interface (granularity 10mb)

class CreditChecker_AT_A1_SMS(CreditChecker):
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
            super().__init__(mobile_atlas_mediator, parser, use_sms = True)
            self.sleep = 60*15 # check credit every 15mins
            self.used_queue = Queue()
            self.used_zero_rated_queue = Queue()

    def sms_received(self, sms: ModemManagerSms):
        try:
            result = re.search('Sie haben seit Abschluss Ihrer letzten Rechnung ca\. (.+?) (.+?) Datenvolumen verbraucht', sms.get_text())
            if result:
                used = result.group(1)
                unit = result.group(2)
                val = f"{used} {unit}"
                used_bytes = convert_size_to_bytes(val)
                self.used_queue.put(used_bytes)
        except:
            pass
        try:
            result = re.search('(.+?)/unlimitiert (.+?) A1 Free Stream NATIONAL', sms.get_text())
            if result:
                used = result.group(1)
                unit = result.group(2)
                val = f"{used} {unit}"
                used_bytes = convert_size_to_bytes(val, decimal_separator=",")
                self.used_zero_rated_queue.put(used_bytes)
        except:
            pass

    def receive_used_units(self):
        self.mobile_atlas_mediator.cleanup() #clean any present sms and calls
        self.used_queue = Queue()
        self.mobile_atlas_mediator.send_sms('421', ' ')
        return self.used_queue.get(timeout=120)

    def receive_used_units_zero_rating(self):
        self.mobile_atlas_mediator.cleanup() #clean any present sms and calls
        self.used_zero_rated_queue = Queue()
        self.mobile_atlas_mediator.send_sms('411', ' ')
        return self.used_zero_rated_queue.get(timeout=120)

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                used_units = self.receive_used_units()
                used_zero_rating = self.receive_used_units_zero_rating()
                billed_units = used_units - used_zero_rating
                ret.traffic_bytes_total = billed_units
                ret.bill_dump = {'used_bytes':used_units, 'free_stream_bytes':used_zero_rating}

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





class CreditChecker_AT_A1(CreditCheckerWeb):
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
    TIMEZONE = timezone('Europe/Vienna')

    URL_INIT = "https://asmp.a1.net/"
    URL_LOGIN = "https://asmp.a1.net/asmp/ProcessLoginServlet/"
    APP_HEADER = {
        "X-Client-Channel": "MEIN-A1-APP",
        "X-Client-Version": "21.5.1"
    }

    # to fetch available config options
    URL_APP_CONFIG = "https://asmp.a1.net/api/v1/mcare/config"
    APP_HEADER_CONFIG_POSTPAID = {
        "X-Client-Profile-Trf": "3.0",
        "X-Client-Profile-Opt": "3.0"
    }
    APP_HEADER_CONFIG_PREPAID = {
        "X-Client-Profile-Bfreetrf": "2.0",
        "X-Client-Profile-Bfreeopt": "1.0"
    }
    #URL_APP_BFREE_GET_TARIFF = "https://asmp.a1.net/api/v1/mcare/bfreetrf/2.0/getMyTariffSummary"
    URL_APP_BATCH_SERVICES = "https://asmp.a1.net//api/v1/mcare/batch"
    PARAM_BILL = {
        "services": {
            "TRF-MYT-SUM": {
                "pathParams": {},
                "queryParams": {},
                "serviceId": "TRF-MYT-SUM",
                "subServiceId": "TRF-MYT-SUM",
                "version": "3.0"
            },
            "BFREETRF-MYT-SUM": {
                "pathParams": {},
                "queryParams": {},
                "serviceId":"BFREETRF-MYT-SUM",
                "subServiceId": "BFREETRF-MYT-SUM",
                "version": "2.0"
            },
            "FUC-GET-MOBILE": {
                "pathParams": {},
                "queryParams": {},
                "serviceId": "FUC-GET-MOBILE",
                "subServiceId": "FUC-GET-MOBILE",
                "version": "2.0"
            }
        },
        "timeoutInMillis": 10000
    }

    URL_WEB_INIT_EXECUTION_FLOW = "https://ppp.a1.net/start/prepaid.sp?execution=e2s1"
    URL_WEB_DOWNLOAD_CSV = "https://ppp.a1.net/start/ajax/evnDownload.sp?flowExecutionKey=e2s1&bsn=-1&filename=laufend&type=csv"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.minimum_billing_unit = 10 * CreditChecker.MEGABYTE
        self.sleep = 60*5 # just checking every 5mins is enough, since we might trigger some serverside code when generating csv
        self.get_phone_number = parser.get_phone_number
        self.base_bill_web = None
        self.base_bill_app = None
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_AT_A1.CONFIG_SCHEMA_CREDIT)

    def get_username(self):
        return self.parser.get_config().get('credit_checker_params.username', None)
    
    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        # login via web
        r = self.s.get(CreditChecker_AT_A1.URL_INIT)
        param = {
            #"userRequestURL": "http%3A%2F%2Fwww.a1.net%2F",
            #"service": "MSSLoginService",
            #"serviceRegistrationURL": "",
            #"level": "10",
            #"wrongLoginType": "false",
            #"SetMsisdn": "false",
            "UserID": self.get_username(),
            "Password": self.get_password()
            #"u2": "u2"
        }
        r = self.s.post(CreditChecker_AT_A1.URL_LOGIN, param)

        #use app api from now on
        self.s.headers.update(CreditChecker_AT_A1.APP_HEADER)
        logger.info("credit_checker loggedin")

    def get_csv_bill_info(self, new_base=False):
        ret = BillInfo()
        r = self.s.get(CreditChecker_AT_A1.URL_WEB_INIT_EXECUTION_FLOW)
        r = self.s.get(CreditChecker_AT_A1.URL_WEB_DOWNLOAD_CSV) #check for status_code because sometimes we get 401?
        #"datum";"beginn";"dauer";"zone/typ";"rufnummer";"volumen up";"volumen down";"netto"
        #"21.07.2021";"13:56:02";"00:20:21";"Datenvolumen";"A1.NET";"2,17 MB";"12,03 MB";"0,00 €"
        csv_str = r.content.decode(r.encoding) #usually 'windows-1252'/'ISO-8859-1'
        csv_str = csv_str.replace('"Diese Liste der Einzelverbindungen ist nicht vollständig, da die Rechnungsperiode noch nicht abgeschlossen ist."', '').strip()
        csv_reader = csv.DictReader(csv_str.splitlines(), delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL)
        #OrderedDict([('datum', '21.07.2021'), ('beginn', '13:56:02'), ('dauer', '00:20:21'), ('zone/typ', 'Datenvolumen'), ('rufnummer', 'A1.NET'), ('volumen up', '2,17 MB'), ('volumen down', '12,03 MB'), ('netto', '0,00 €')])
        info = []
        for row in csv_reader:
            zone = row.get('zone/typ')
            if "Daten" in zone: #alternative ('rufnummer', 'A1.NET')
                new_entry = {}
                con_date = row.get('datum')
                con_time = row.get('beginn')
                timestamp = f"{con_date} {con_time}"
                timestamp = datetime.strptime(timestamp, '%d.%m.%Y %H:%M:%S')
                timestamp = CreditChecker_AT_A1.TIMEZONE.localize(timestamp).astimezone(pytz.utc)
                new_entry['timestamp_start'] = timestamp

                bytes_up = convert_size_to_bytes(row.get('volumen up'), decimal_separator=",")
                bytes_down = convert_size_to_bytes(row.get('volumen down'), decimal_separator=",")
                new_entry['bytes_up'] = bytes_up
                new_entry['bytes_down'] = bytes_down

                #cost = float(row.get('netto').replace("€", '').replace(",", ".").strip())
                info.append(new_entry)

        if new_base:
            self.base_bill_csv = info
        new_entries = CreditCheckerWeb.subtract_list_of_dict(info, self.base_bill_csv)
        date_old_entries = self.parser.startup_time - relativedelta(minutes=5)   # discard entries that are from old sessions
        new_entries = [x for x in new_entries if x.get('timestamp_start') > date_old_entries]
        if len(info):
            latest_entry = max(info, key=lambda e: e['timestamp_start'])
            ret.timestamp_effective_date = latest_entry.get("timestamp_start", None)
        ret.traffic_bytes_upstream = sum(map(lambda x: int(x['bytes_up']), new_entries))
        ret.traffic_bytes_downstream = sum(map(lambda x: int(x['bytes_down']), new_entries))
        ret.traffic_bytes_total = ret.traffic_bytes_upstream + ret.traffic_bytes_downstream
        ret.traffic_cnt_connections = len(new_entries)
        return ret

    def get_app_bill_info(self, new_base=False):
        ret = BillInfo()
        r = self.s.post(CreditChecker_AT_A1.URL_APP_BATCH_SERVICES, json=CreditChecker_AT_A1.PARAM_BILL)
        resp_json = benedict(r.json().get('content', {}))
        ret.bill_dump = resp_json
        #effective_date = resp_json.get('BFREETRF-MYT-SUM.content.data.timeOfRetrieval', None)
        # effective date that is displayed at website actually is no effective date <.<
        #if effective_date:
        #    ret.timestamp_effective_date = CreditChecker.iso8601_to_utc(effective_date)
        bills = resp_json.get('FUC-GET-MOBILE.content.data.other', [])
        for b in bills:
            if b.get('category') == 'DATA' and 'Free Stream' not in b.get('description'):
                # straight forward way, by using data that is reported in GB with two decimal points (--> granularity 10mb <.<)
                used = b.get('currentUsed', None)
                unit = b.get('unit', None)
                #desc = b.get('description', None)
                if unit and used is not None:
                    val = f"{used} {unit}"
                    used_bytes = convert_size_to_bytes(val)
                    ret.traffic_bytes_total = used_bytes
                # workarround: use percentage (from total quota) to calculate used bytes, since that should give us ~1mb granularity; does not work...
                #avail = b.get('currentAvailable', None)
                #unit = b.get('unit', None)
                #percentageUsed = b.get('currentPercentageUsed', None)
                #if all(x is not None for x in [avail, unit, percentageUsed]):
                #    val = f"{avail} {unit}"
                #    avail_bytes = convert_size_to_bytes(val)
                #    used_bytes = percentageUsed*avail_bytes / 100
                #    ret.traffic_bytes_total = sum(filter(None, [ret.traffic_bytes_total, used_bytes])) #add to bytes_total
        if new_base:
            self.base_bill_app = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill_app)
        return ret

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()
                bill_app = self.get_app_bill_info(new_base)
                #bill_csv = self.get_csv_bill_info(new_base)

                # prfer csv dump as return value, but include both dumps to verbose dump info
                ret = bill_app
                #bill_dump = {}
                #bill_dump["APP"] = bill_app.bill_dump 
                #bill_dump["CSV"] = bill_csv.bill_dump 
                #ret.bill_dump = bill_dump

                #if not bill_csv.traffic_bytes_total and bill_app.traffic_bytes_total:
                #    logger.info("traffic info availible in app but not in csv?!")
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