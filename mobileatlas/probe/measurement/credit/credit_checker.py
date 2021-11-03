import decimal
from mobileatlas.probe.measurement.utils.format_logging import format_extra
import time
import logging
import pytz
from decimal import *
from datetime import datetime
from pytz import timezone
from dateutil.relativedelta import relativedelta
from jsonschema.exceptions import by_relevance
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.mediator.mobile_atlas_plugin import MobileAtlasPlugin
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator

logger = logging.getLogger(__name__)

class BillInfo:
    def __init__(self):
        self.credit_consumed_credit: Decimal = None
        self.traffic_bytes_total: int = None
        self.traffic_bytes_upstream: int = None
        self.traffic_bytes_downstream: int = None
        self.traffic_cnt_connections: int = None
        self.timestamp_effective_date: datetime = None
        self.bill_dump = None

    def to_dict(self):
        return vars(self)

    def subtract_base_bill(self, base):
        for k, v in vars(self).items():
            b = vars(base).get(k, None)
            if k == 'timestamp_effective_date' or k == 'bill_dump':
                continue
            elif all([v,b]):
                setattr(self, k, v - b)

    def add_consumed_units(self, units):
        for k, v in units.items():
            cur_val = getattr(self, k, None)
            if cur_val is None:
                cur_val = 0
            setattr(self, k, cur_val + v)

class CreditChecker(MobileAtlasPlugin):
    # sleep 60 seconds when waiting for bill
    DEFAULT_SLEEP = 60
    # abort when no credit is billed for 10h
    DEFAULT_TIMEOUT = 3600*10
    # return when effectivetime of bill is older then 10min
    DEFAULT_TIME_DELTA = 600

    BASE = 1024
    KILOBYTE = BASE
    MEGABYTE = BASE * BASE

    # 1 megabyte is default resolution
    DEFAULT_BYTES = 1 * MEGABYTE


    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "sleep" : {"type" : "integer"},
                    "timeout" : {"type" : "integer"},
                    "effective_time_delta" : {"type" : "integer"}, # set to 0 to turn off
                }
            }
        }
    }

    LOGGER_TAG = "credit_checker"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser, use_sms = False, use_call = False, use_ussd = False, use_connection = False, use_internet_gw = False):
        super().__init__(mobile_atlas_mediator, use_sms = use_sms, use_call=use_call, use_ussd = use_ussd, use_connection=use_connection, use_internet_gw=use_internet_gw)
        self.parser = parser
        self.minimum_billing_unit = 1 * CreditChecker.MEGABYTE
        self.connectionwise_billing_available = False
        self.sleep = CreditChecker.DEFAULT_SLEEP
        self.timeout = CreditChecker.DEFAULT_TIMEOUT
        self.time_delta = CreditChecker.DEFAULT_TIME_DELTA
        self.base_bill = None
        self.current_bill = None
        self.tag = CreditChecker.LOGGER_TAG
        self.validate_credit_checker_config()
        self.result_logger = logging.getLogger("RESULTS")
        self.traffic_minimum_bytes = CreditChecker.DEFAULT_BYTES
        self.consumed_credit = BillInfo()

    def add_consumed_units(self, unit_dict):
        self.consumed_credit.add_consumed_units(unit_dict)
        logger.debug(f"added consumed units to credit checker: {unit_dict}", extra=format_extra('add_consumed_units', {'added_units': unit_dict, 'total_consumed_units' : self.consumed_credit.to_dict()}))
        
    def validate_credit_checker_config(self):
        self.parser.validate_test_config_schema(CreditChecker.CONFIG_SCHEMA_CREDIT)
    
    def supports_connectionwise_billing(self):
        return self.connectionwise_billing_available

    def get_minimum_billing_unit(self):
        return self.minimum_billing_unit

    def add_snapshot_billed_credit(self):
        logger.debug("billed_credit", extra=self.current_bill.to_dict())

    def get_sleep(self):
        return self.parser.get_config().get('credit_checker_params.sleep', self.sleep)

    def get_timeout(self):
        return self.parser.get_config().get('credit_checker_params.timeout', self.timeout)

    def get_effective_time_delta(self):
        return self.parser.get_config().get('credit_checker_params.effective_time_delta', self.time_delta)

    def get_traffic_minimum_bytes(self):
        return self.traffic_minimum_bytes
    
    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        pass

    def retrieve_current_bill(self, new_base = False, retry = 5):
        if self.base_bill is None:
            new_base = True
        self.setup_callbacks()
        ret = self._retrieve_current_bill(new_base)
        self.add_snapshot_billed_credit()
        self.remove_callbacks()
        return ret

    def wait_for_bill(self, billed_units=None):
        if billed_units is None:
            billed_units = vars(self.consumed_credit)
        start_time = datetime.now(pytz.utc)
        if self.get_effective_time_delta() is not None:
            billed_units['timestamp_effective_date'] = datetime.now(pytz.utc) + relativedelta(seconds=self.get_effective_time_delta())
        while True:
            ret = self.retrieve_current_bill()
            bill = ret.to_dict()
            logger.info(f"current bill is {bill.get('traffic_bytes_total')} bytes, waiting for {self.consumed_credit.to_dict()}", extra=format_extra('wait_for_bill', {'current_bill': bill, 'consumed_credit' : self.consumed_credit.to_dict()}))
            if CreditChecker.is_requirement_fullfilled(ret, billed_units):
                time_from_start = datetime.now(pytz.utc) - self.parser.get_startup_time()
                time_from_stop = datetime.now(pytz.utc) - start_time

                del bill['bill_dump']   #delete verbose bill_dump to not bloat logs and results
                self.result_logger.info("billed units recognized", extra=format_extra('billed_credit', {'duration_from_test_start':time_from_start, 'duration_from_test_stop': time_from_stop, 'current_bill': bill, 'consumed_credit' : self.consumed_credit}))
                return ret
            elif datetime.now(pytz.utc) > start_time + relativedelta(seconds=self.get_timeout()):
                raise TimeoutError("Timeout when waiting for traffic...")
            time.sleep(self.get_sleep())

    @staticmethod
    def is_requirement_fullfilled(bill: BillInfo, requirement):
        for k, v1 in vars(bill).items():
            v2 = requirement.get(k, None)
            if all([v1,v2]) and v1 >= v2:
                return True

    @staticmethod
    def iso8601_to_utc(date_str, msecs=False):
        if msecs:
            return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S.%f%z').astimezone(pytz.utc)#.replace(tzinfo=None)
        return datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S%z').astimezone(pytz.utc)#.replace(tzinfo=None)

    def round_to_unit(value, unit, decimals=0, round_mode="default"):
        rounding_modes = {
            "up": decimal.ROUND_UP,
            "down":  decimal.ROUND_DOWN,
            "default" : decimal.ROUND_HALF_EVEN
        }
        with decimal.localcontext() as ctx:
            d = decimal.Decimal(value / unit)
            ctx.rounding = rounding_modes.get(round_mode, decimal.ROUND_HALF_EVEN)
            return round(d, decimals) * unit