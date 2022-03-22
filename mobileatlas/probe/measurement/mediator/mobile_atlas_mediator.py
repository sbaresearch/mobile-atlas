#!/usr/bin/env python3
from pathlib import Path
import psutil
from mobileatlas.probe.measurement.mediator.nm_definitions import DeviceState, DeviceStateReason
from mobileatlas.probe.measurement.mediator.mm_definitions import Modem3gppRegistrationState, Modem3gppUssdSessionState, ModemManagerSms, ModemState, ModemStateChangeReason, SmsState
import os
import json
import time
import logging
from datetime import datetime
from threading import Event, Thread, Lock
from mobileatlas.probe.measurement.utils.format_logging import format_extra

#import gi
#gi.require_version('ModemManager', '1.0')
from gi.repository import GLib
from .modem_watcher import MMCallbackClass, ModemWatcher
from .network_watcher import NetworkWatcher, NMCallbackClass
from ..utils.event_utils import EnhancedEvent

logger = logging.getLogger(__name__)

#needs to run to receive event callbacks etc
class GLibRunner(Thread):
    def __init__(self):
        Thread.__init__(self)
        self.main_loop = GLib.MainLoop()

    def run(self):
        self.main_loop.run()

    def stop(self):
        self.main_loop.quit()

class MobileAtlasMediator(MMCallbackClass, NMCallbackClass):
    DIR_LOG = "/tmp/mobileatlas"
    LOGGER_TAG = "mobile_atlas_mediator"
    MODEM_NETWORK_INTERFACE_NAME = 'ppp0'

    def __init__(self, modem_type):
        self.modem_type = modem_type
        self.main_loop = GLibRunner()

        path = Path(MobileAtlasMediator.DIR_LOG)
        filename = f"test_{datetime.now():%Y%m%d-%H%M%S}.log"

        path.mkdir(parents=True, exist_ok=True)    #ensure the directory exists
        self.logfile = path / filename

        self.log_json = {}

        self.veth_bridge_usecnt = 0
        self.veth_bridge_lock = Lock()
        
        self.veth_gw_usecnt = 0
        self.veth_gw_lock = Lock()

        self.modem_added = Event()
        self.modem_enabled = EnhancedEvent()
        self.modem_registered = EnhancedEvent()
        self.modem_connected = EnhancedEvent()
        self.modem_nm_disconnected = Event()
        self.connection = None

        self.mm = ModemWatcher(self)
        self.nm = NetworkWatcher(self)
        self.mm_modem_state = ModemState.UNKNOWN
        self.nm_modem_state = DeviceState.UNKNOWN

        self.sms_observer = []
        self.connection_observer = []
        self.ussd_observer = []

    def start(self):
        self.main_loop.start()

    def shutdown(self):
        self.main_loop.stop()

    def nm_modem_added(self, udi):
        logger.info('nm_modem_added', extra=format_extra('nm_modem_added', {'udi' : udi}))

    def nm_modem_removed(self, udi):
        logger.info('nm_modem_removed', extra=format_extra('nm_modem_removed', {'udi' : udi}))

    def nm_modem_state_changed(self, udi, old_state: DeviceState, new_state: DeviceState, reason: DeviceStateReason):
        log_msg = f"nm_modem_state_changed: {old_state} -> {new_state}"
        logger.info(log_msg, extra=format_extra("nm_modem_state_changed", {'udi' : udi, 'old_state': old_state, 'new_state': new_state, 'reason': reason, 'nm_device_config' : self.nm.get_config_for_device(udi)}))
        self.nm_modem_state = new_state
        if new_state == DeviceState.DISCONNECTED:
            self.modem_nm_disconnected.set()
        else:
            self.modem_nm_disconnected.clear()
        # combine mm state info with nm state info
        self.connection_state_changed()

    def mm_modem_added(self, modem_path):
        logger.info('mm_modem_added', extra=format_extra('mm_modem_added', {'modem_path' : modem_path}))
        self.modem_added.set()

    def mm_modem_removed(self, modem_path):
        logger.info('mm_modem_removed', extra=format_extra('mm_modem_removed', {'modem_path' : modem_path}))
        self.modem_added.clear()    #will actually not work when working with multiple modems...

    def mm_modem_sms_state_changed(self, sms: ModemManagerSms):
    #def mm_modem_sms_state_changed(self, modem_path, message_path, number, timestamp, text, state):
        log_msg = f"mm_modem_sms_state_changed {sms.get_path()}: {sms.get_number()} ({sms.get_timestamp()}): {sms.get_text()}"
        logger.info(log_msg, extra=format_extra('mm_modem_sms_state_changed', {'sms': sms}))
        state = sms.get_state()
        if state == SmsState.RECEIVED or state == SmsState.SENT:
            self.notify_sms_subscriber(sms)

    def mm_modem_state_changed(self, modem_path, old_state: ModemState, new_state: ModemState, reason: ModemStateChangeReason):
        log_msg = f"mm_modem_state_changed: {old_state} -> {new_state}"
        logger.info(log_msg, extra=format_extra('mm_modem_state_changed', {'modem_path' : modem_path, 'old_state': old_state, 'new_state': new_state, 'reason': reason, 'mm_modem_config' : self.mm.get_config_for_modem(modem_path)}))
        self.mm_modem_state = new_state
        # check if modem is enabled, registered
        self.modem_state_changed()
        # combine mm state info with nm state info
        self.connection_state_changed()

    def mm_modem_call_added(self, modem_path, call_path, number, direction, state, state_reason):
        log_msg = f"mm_modem_call_received {call_path}: ({number}) -> {state} - {state_reason}"
        logger.info(log_msg, extra=format_extra('mm_modem_call_received', {'modem_path' : modem_path, 
                           'call_path': call_path, 'number': number, 'direction': direction, 'state': state, 'state_reason': state_reason}))

    def mm_modem_call_state_changed(self, modem_path, call_path, old_state, new_state, reason):
        log_msg = f"mm_modem_call_state_changed {call_path}: {old_state} -> {new_state}"
        logger.info(log_msg, extra=format_extra('mm_modem_call_state_changed', {'modem_path' : modem_path, 
                           'call_path': call_path, 'old_state': old_state, 'new_state': new_state, 'reason': reason}))

    def mm_modem_ussd_notification_changed(self, modem_path, state: Modem3gppUssdSessionState, message: str):
        log_msg = 'mm_modem_ussd_notification_changed', {'state': state, 'message': message}
        logger.info(log_msg, extra=format_extra('mm_modem_ussd_notification_changed', {'modem_path' : modem_path, 'state': state, 'message': message}))
        if message:
            self.notify_ussd_subscriber(message)

    def is_modem_enabled(self):
        return self.mm_modem_state >= ModemState.ENABLED
    
    def is_modem_registered(self):
        return self.mm_modem_state >= ModemState.REGISTERED

    def is_modem_connected(self):
        return self.mm_modem_state >= ModemState.CONNECTED

    def is_modem_device_connected(self):
        return self.nm_modem_state == DeviceState.ACTIVATED

    def is_home_network(self):
        state = self.mm.get_modem_registration_state()
        return state == Modem3gppRegistrationState.HOME

    def wait_modem_added(self, timeout = 120):
        if not self.modem_added.wait(timeout):
            raise TimeoutError("No modem was found (timeout expired)")

    #def wait_modem_registered(self, timeout = 300, preserve_state_timeout = None):
    #    start_time = time.time()
    #    # wait for modem to get into registred state
    #    logger.debug(f"Wait until modem is in registered state, timeout after {timeout} seconds...")
    #    if not self.modem_registered.wait(timeout):
    #        # throw timeout error in case modem does not get into registered state in time
    #        logger.debug("Modem is not registered in network (timeout expired)")
    #        raise TimeoutError(
    #            "Modem is not registered in network (timeout expired)")
    #    # if modem is registered and preserve timeout is defined the modem need to stay into registered state for xx seconds before the function returns
    #    # if modem is registered and preserve timeout is None the function just returns
    #    elif preserve_state_timeout is not None:
    #        logger.debug(f"Modem is not registered, wait {preserve_state_timeout} seconds and make sure it stays in registered state")
    #        # wait preservation time and see if modem deregisters from network again
    #        if self.modem_registered.wait_cleared(preserve_state_timeout):
    #            logger.debug("Modem is unregistered again...start over...")
    #            # modem is in unregistreed state again :-/
    #            # calculate how many seconds have passed since initial call and start over again with the amount of time that is left
    #            time_elapsed = (time.time() - start_time)  ## xx seconds of timeout alreay passed
    #            time_left = timeout - time_elapsed
    #            return self.modem_registered(time_left, preserve_state_timeout)
    def wait_modem_registered(self, timeout = 1800, preserve_state_timeout = 0):
        logger.debug(f"Ensure modem is in registered state, timeout after {timeout} seconds...")
        if not self.modem_registered.wait_debounced(timeout, preserve_state_timeout):
            logger.debug("Modem is not registered in network (timeout expired)")
            raise TimeoutError("Modem is not registered in network (timeout expired)")

    def wait_modem_enabled(self, timeout = 1800, preserve_state_timeout = 0):
        logger.debug(f"Ensure modem is enabled, timeout after {timeout} seconds...")
        if not self.modem_enabled.wait_debounced(timeout, preserve_state_timeout):
            logger.debug("Modem is not enabled (timeout expired)")
            raise TimeoutError("Modem is not enabled (timeout expired)")

    def wait_modem_connected(self, timeout = 15, preserve_state_timeout = 5):
        logger.debug(f"Wait until connection is established, timeout after {timeout} seconds...")
        if not self.modem_connected.wait_debounced(timeout, preserve_state_timeout, False):
            logger.debug("Modem not connected...")
            return False
        return True
        #if not self.modem_connected.wait(timeout):
        #    logger.error("Modem is still not connected (timeout expired)")
        #    # return false in case modem does not come into connected state
        #    return False
        #elif preserve_state_timeout is not None:
        #    logger.debug(f"Connection established, wait {preserve_state_timeout} seconds and make sure it stays connected")
        #    # return false in case modem disconnects again
        #    if self.modem_connected.wait_cleared(preserve_state_timeout):
        #        logger.error("Disconnected...")
        #        return False
        # otherwise return true
        #return True

    def modem_state_changed(self):
        #is modem enabled?
        old_state = self.modem_enabled.is_set()
        modem_enabled = self.is_modem_enabled()
        if modem_enabled:
            self.modem_enabled.set()
        else:
            self.modem_enabled.clear()

        # is modem registered
        old_state = self.modem_registered.is_set()
        modem_registered = self.is_modem_registered()
        if modem_registered:
            self.modem_registered.set()
        else:
            self.modem_registered.clear()

    def connection_state_changed(self):
        old_state = self.modem_connected.is_set()
        mm_connected = self.is_modem_connected()
        nm_connected = self.is_modem_device_connected()
        new_state = all([mm_connected, nm_connected])
        if new_state:
            # modem is connected!
            self.modem_connected.set()
        else:
            # modem is disconnected
            self.modem_connected.clear()
        if new_state != old_state:
            self.notify_connection_subscriber(new_state)

    def send_ussd_code(self, code="*101#"):
        return self.mm.send_ussd_code(code)

    def change_charset(self, charset="UCS2"):
        return self.mm.change_charset(charset)

    def send_ussd_code_at(self, code="*101#"):
        command = f"AT+CUSD=1,{code},15"
        self.mm.send_at_command(command=command, timeout=10)

    def send_at_command(self, command):
        return self.mm.send_at_command(command=command, timeout=10)

    def disable_rf(self):
        return self.mm.disable_rf()

    def send_sms(self, number, text):
        return self.mm.send_sms(number=number, text=text)

    def clear_pdp_context_list(self):
        self.mm.clear_pdp_context_list()

    def apply_hotfixes(self):
        # TODO: find better way to handle specific modem types (maybe factory-wise approach like creditchecker)
        if self.modem_type == "quectel":    
            # hotfix: clear pdp list since modemmanager/pppd doesn't work correctly when there are >10 pdp contexts >.<
            self.clear_pdp_context_list()
            # hotfix: set charset to ucs2 to get modemmanagers ussd code work out of the box
            self.change_charset(charset="UCS2")
        #TODO: if driver != option
        os.system("ip netns exec default ip link set wwan0 netns ns_mobileatlas")

    def connect_modem(self, apn=None, username=None, password=None, pdp_type=None, network_id=None, connection_timeout = 20, connected_preservation_time = 5, registration_timeout = 60, registered_preservation_time = None, retries=10, cooldown=10):
        if self.modem_connected.is_set():
            raise ValueError("Modem is already connected...")

        for i in range(retries):
            logger.debug(f"Connect modem, loopCnt: {i}")
            # modem needs to be in registered state --> otherwise makes no sense to register
            self.wait_modem_registered(registration_timeout, registered_preservation_time)

            #add temporary connection if neccessary
            if self.connection is None:
                self.connection = self.nm.create_connection(
                    "temp", apn, username, password, pdp_type, network_id)
                self.nm.connect_device(self.connection)
            else:
                self.nm.send_connect_device("temp")

            if self.wait_modem_connected(connection_timeout, connected_preservation_time): # modem is connected --> return :)
                return
            elif i < retries:
                logger.debug(f"Sleep {cooldown} seconds and try to connect again")
                time.sleep(cooldown)
        logger.error("Could not connect modem...")
        raise RuntimeError("Could not connect modem...")

    def get_network_config(self):
        nm_config = self.nm.get_config_for_device()
        #logger.debug(json.dumps(nm_config, indent=4))
        return nm_config

    def get_modem_config(self):
        mm_config = self.mm.get_config_for_modem()
        #logger.debug(json.dumps(mm_config, indent=4))
        return mm_config

    def _enable_veth_bridge(self):
        # sometimes bridge is not added properly, just readd it here again... :X
        #os.system("ip link add veth0 type veth peer name veth1 netns default")
        #os.system("ip netns exec default ip link set veth1 up")
        #os.system("ip netns exec default ip addr add 10.29.183.2/24 dev veth1")
        #os.system("ip netns exec default ip route add 10.29.183.0/24 dev veth1")
        # actually this should be enought:
        os.system("ip link set veth0 up")
        os.system("ip addr add 10.29.183.1/24 dev veth0")

    def _disable_veth_bridge(self):
        os.system("ip link set veth0 down")

    # TODO: use pyroute2 lib?
    def _enable_veth_gateway(self):
        os.system("route add default gw 10.29.183.2")

    def _disable_veth_gateway(self):
        os.system("route delete default gw 10.29.183.2")

    # TODO: use Semaphore class instead of Lock + Cnt?
    def enable_veth_bridge(self):
        with self.veth_bridge_lock:
            if self.veth_bridge_usecnt <= 0:
                self._enable_veth_bridge()
            self.veth_bridge_usecnt += 1
    
    def disable_veth_bridge(self):
        with self.veth_bridge_lock:
            self.veth_bridge_usecnt -= 1
            if self.veth_bridge_usecnt <= 0:
                self._disable_veth_bridge()
                self.veth_bridge_usecnt = 0

    def enable_veth_gateway(self):
        with self.veth_gw_lock:
            self.enable_veth_bridge()
            if self.veth_gw_usecnt <= 0:
                self._enable_veth_gateway()
            self.veth_gw_usecnt += 1
    
    def disable_veth_gateway(self):
        with self.veth_gw_lock:
            self.disable_veth_bridge()
            self.veth_gw_usecnt -= 1
            if self.veth_gw_usecnt <= 0:
                self._disable_veth_gateway()
                self.veth_gw_usecnt = 0
                
    def get_current_bytes(self, interface=None):
        if interface is None:
            interface = MobileAtlasMediator.MODEM_NETWORK_INTERFACE_NAME
        if self.modem_connected.is_set():
            traffic = psutil.net_io_counters(pernic=True, nowrap=False).get(interface)   #might threw exception if interface is not up...
            return traffic.bytes_recv, traffic.bytes_sent
        return 0

    def io_counter_to_json(self, traffic):
        # snetio(bytes_sent=14508483, bytes_recv=62749361, packets_sent=84311, packets_recv=94888, errin=0, errout=0, dropin=0, dropout=0)
        json = {
            'bytes_sent': traffic.bytes_sent,
            'bytes_recv': traffic.bytes_recv,
            'packets_sent': traffic.packets_sent,
            'packets_recv': traffic.packets_recv,
            'err_in': traffic.errin,
            'err_out': traffic.errout,
            'drop_in': traffic.dropin,
            'drop_out': traffic.dropout,
        }
        return json
        
    def get_network_interface_snapshot(self):
        if_list = []
        interface_dict = psutil.net_io_counters(pernic=True, nowrap=False)
        for key, value in interface_dict.items():
            if_list.append({ key : self.io_counter_to_json(value)})
        return if_list

    def write_logfile(self):
        logger.debug(f"writing logfile...")
        with open(self.logfile, "w") as f:
            json_str = json.dumps(self.log_json, sort_keys=True, indent=2, default=str)
            f.write(json_str)
            logger.info(f"wrote log to json-file {self.logfile}...")

    def disconnect_modem(self, timeout=30):
        self.nm.disconnect()
        if not self.modem_nm_disconnected.wait(timeout):
            raise TimeoutError(f"Modem did not disconnect within {timeout} seconds...")

    # delete all calls and sms that are saved
    def cleanup(self):
        self.mm.wipe_messages()
        self.mm.wipe_calls()

    def log(self, event_name, extra=None, tag=None, event_key = LOGGER_TAG):
        # in case the event key does not exist yet, create an empty array
        if self.log_json.get(event_key, None) is None:
            self.log_json[event_key] = []
        event = {}
        event['event'] = event_name
        event['timestamp'] = datetime.now()
        if tag:
            event['tag'] = tag
        if extra:
            event['params'] = extra
        self.log_json[event_key].append(event)

    def set_log_element(self, key, value):
        self.log_json[key] = value

    def add_sms_observer(self, observer):
        self.sms_observer.append(observer)
    
    def notify_sms_subscriber(self, sms: ModemManagerSms):
        for observer in self.sms_observer:
            observer(sms)
    
    def remove_sms_observer(self, observer):
        self.sms_observer.append(observer)

    def add_connection_observer(self, observer):
        self.connection_observer.append(observer)
    
    def notify_connection_subscriber(self, is_connected):
        for observer in self.connection_observer:
            observer(is_connected)

    def remove_connection_observer(self, observer):
        self.connection_observer.append(observer)

    def add_ussd_observer(self, observer):
        self.ussd_observer.append(observer)
    
    def notify_ussd_subscriber(self, notification_string):
        for observer in self.ussd_observer:
            observer(notification_string)

    def remove_ussd_observer(self, observer):
        self.ussd_observer.append(observer)