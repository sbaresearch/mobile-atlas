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

#sms_state_changed /org/freedesktop/ModemManager1/SMS/0: 448 (2022-03-18T12:34:44+01:00): Stanje na racunu je: 5.00 EUR. Racun velja do: 16.06.2022. Iz zakupa A1 Simpl mali je na voljo se 498 enot. Enote so veljavne do 17.04.2022. V EU/EEA gostovanju je na voljo se 500.00 MB. A
class CreditChecker_SI_A1(CreditChecker):
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
