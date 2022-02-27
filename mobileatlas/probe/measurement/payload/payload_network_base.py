
from mobileatlas.probe.measurement.utils.format_logging import format_extra
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from threading import Event
from mobileatlas.probe.measurement.test.test_network_base import TestNetworkBase
from .payload_base import PayloadBase, PayloadResult
from operator import sub
import logging

logger = logging.getLogger(__name__)

class PayloadNetworkResult(PayloadResult):
    def __init__(self, success, result, consumed_bytes_rx, consumed_bytes_tx, request_cnt):
        self.success = success
        self.result = result
        self.consumed_bytes_rx = consumed_bytes_rx
        self.consumed_bytes_tx = consumed_bytes_tx
        self.request_cnt = request_cnt


class PayloadNetworkBase(PayloadBase):
    LOGGER_TAG = "payload_network_base"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, use_sms = False, use_call = False, use_ussd = False, use_connection = True, use_internet_gw = False, payload_size=None):
        super().__init__(mobile_atlas_mediator, use_sms = use_sms, use_call = use_call, use_ussd = use_ussd, use_connection = use_connection, use_internet_gw = use_internet_gw)
        self.tag = PayloadNetworkBase.LOGGER_TAG
        # event is set in case modem disconnected during measurement
        self.modem_disconnected = Event()
        self.get_current_bytes = self.mobile_atlas_mediator.get_current_bytes
        self.payload_size = payload_size
        self.traffic_start = None
        self.traffic_stop = None

    def connection_state_changed(self, is_connected):
        if not is_connected:
            self.modem_disconnected.set()

    def send_payload(self) -> PayloadNetworkResult:
        pass

    def add_network_interface_snapshot(self, tag):
        snapshot = self.mobile_atlas_mediator.get_network_interface_snapshot()
        logger.debug(f'network_interface_snapshot: {tag}', extra=format_extra(tag, {'snapshot': snapshot}))

    def get_consumed_bytes(self):
        if self.traffic_stop:
            stop = self.traffic_stop
        else:
            stop = self.get_current_bytes()
        consumed = tuple(map(sub, stop, self.traffic_start))
        return consumed

    def get_missing_bytes(self):
        if self.payload_size == None:
            return 0
        return self.payload_size - sum(self.get_consumed_bytes()) # can be negative when more consumed than needed

    def is_payload_consumed(self):
        return self.payload_size == None or sum(self.get_consumed_bytes()) >= self.payload_size

    def execute(self):
        assert self.mobile_atlas_mediator.modem_connected.is_set(), "Modem needs to be connected when sending network payload"
        self.add_network_interface_snapshot("networkpayload_start")
        self.setup_callbacks()
        self.traffic_stop = None
        self.traffic_start = self.get_current_bytes()
        ret = self.send_payload()
        self.traffic_stop = self.get_current_bytes()
        self.remove_callbacks()
        self.add_network_interface_snapshot("networkpayload_stop")
        assert self.modem_disconnected.is_set() == False, "Modem disconnected during payload"
        return ret

