#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2014 Aleksander Morgado <aleksander@aleksander.es>
# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import re
import time
import gi

gi.require_version('ModemManager', '1.0')
from gi.repository import Gio, GLib, ModemManager
from mobileatlas.probe.measurement.mediator.mm_definitions import CallStateReason, Modem3gppRegistrationState, Modem3gppUssdSessionState, ModemManagerCall, ModemManagerSms, ModemState, ModemStateChangeReason, CallState

class MMCallbackClass:
    def mm_modem_added(self, modem_path):
        raise NotImplementedError("method not implemented")

    def mm_modem_removed(self, modem_path):
        raise NotImplementedError("method not implemented")

    def mm_modem_state_changed(self, modem_path, old_state: ModemState, new_state: ModemState, reason: ModemStateChangeReason):
        raise NotImplementedError("method not implemented")

    def mm_modem_sms_state_changed(self, sms: ModemManagerSms):
        raise NotImplementedError("method not implemented")

    def mm_modem_call_added(self, call: ModemManagerCall):
        raise NotImplementedError("method not implemented")

    def mm_modem_call_state_changed(self, call: ModemManagerCall, old: CallState, new: CallState):
        raise NotImplementedError("method not implemented")

    def mm_modem_ussd_notification_changed(self, modem_path, state: Modem3gppUssdSessionState, message: str):
        raise NotImplementedError("method not implemented")

# struct to save info about modem
#ModemInfo = namedtuple("ModemInfo", "obj awaiting_messages modem_state_changed_id sms_notify_id")


class ModemInfo:
    def __init__(self, obj, modem_state_changed_id=None, sms_added_id=None, call_added_id=None, ussd_notification_added=None):
        self.obj = obj
        self.modem_state_changed_id = modem_state_changed_id
        self.sms_added_id = sms_added_id
        self.call_added_id = call_added_id
        self.ussd_notification_added = ussd_notification_added


"""
The ModemWatcher class is responsible for monitoring ModemManager
https://valadoc.org/libmm-glib/index.htm
"""


class ModemWatcher:

    """
    Constructor
    """

    def __init__(self, callback=None):
        # Flag for initial logs
        self.initializing = True
        # Setup DBus monitoring
        self.connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.manager = ModemManager.Manager.new_sync(self.connection,
                                                     Gio.DBusObjectManagerClientFlags.DO_NOT_AUTO_START,
                                                     None)

        self.callback_obj = callback

        # IDs for added/removed signals
        self.object_added_id = 0
        self.object_removed_id = 0

        self.objects = dict()  # key value pair with object, namedtuple

        # Follow availability of the ModemManager process
        self.available = False
        self.manager.connect('notify::name-owner', self.on_name_owner)
        self.on_name_owner(self.manager, None)
        # Finish initialization
        self.initializing = False

    """
    ModemManager is now available
    """

    def set_available(self):
        # if self.available == False or self.initializing == True:
        #    print('[ModemWatcher] ModemManager service is available in bus')
        self.object_added_id = self.manager.connect(
            'object-added', self.on_object_added)
        self.object_removed_id = self.manager.connect(
            'object-removed', self.on_object_removed)
        self.available = True
        # Initial scan
        if self.initializing == True:
            for obj in self.manager.get_objects():
                self.on_object_added(self.manager, obj)

    """
    ModemManager is now unavailable
    """

    def set_unavailable(self):
        # if self.available == True or self.initializing == True:
        #    print('[ModemWatcher] ModemManager service not available in bus')
        if self.object_added_id:
            self.manager.disconnect(self.object_added_id)
            self.object_added_id = 0
        if self.object_removed_id:
            self.manager.disconnect(self.object_removed_id)
            self.object_removed_id = 0
        # clear/remove all modem objects:
        self.remove_modem_from_list()
        self.available = False

    """
    Name owner updates
    """

    def on_name_owner(self, manager, prop):
        if self.manager.get_name_owner():
            self.set_available()
        else:
            self.set_unavailable()

    """
    Object added
    """

    def on_object_added(self, manager, obj):
        modem = obj.get_modem()
        if modem.get_state() == ModemManager.ModemState.FAILED:
            print('[ModemWatcher,%s] ignoring failed modem' %
                  obj.get_object_path())
            pass
        self.add_modem_to_list(obj)
        # print('[ModemWatcher] %s (%s) modem managed by ModemManager [%s]: %s' %
        #      (modem.get_manufacturer(),
        #       modem.get_model(),
        #       modem.get_equipment_identifier(),
        #       obj.get_object_path()))

    """
    Object removed
    """

    def on_object_removed(self, manager, obj):
        #print('[ModemWatcher] modem unmanaged by ModemManager: %s' % obj.get_object_path())
        self.remove_modem_from_list(obj)

    """
    Status change callback
    """

    def on_state_notify(self, modem, old_state, new_state, reason, modem_obj):
        reason_str = ModemManager.ModemStateChangeReason.get_string(reason)
        modem_info = self.objects.get(modem_obj)
        if modem_info:
            self.connect_modem_signals(modem_info) #sometimes modem arrive in unavailable state and signals can not instantly be subscribed when modem is added
        #print('[ModemWatcher] modem state changed: %s' % new_state_str)
        if self.callback_obj != None:
            self.callback_obj.mm_modem_state_changed(
                modem_obj.get_object_path(), ModemState(old_state), ModemState(new_state), ModemStateChangeReason(reason))

    """
    Messaging callback
    """

    def on_sms_state_changed(self, sms, state, sms_obj, modem_obj, received):
        #print("on_sms_notfiy")
        #messages = messaging.list_sync()
        #sms = self.find_obj_via_path(sms_path, messages)
        #state = ModemManager.SmsState.get_string(sms.get_state())
        #print(state)
        #if state == "received" or state == "sent":
        if self.callback_obj != None:
            callback_param = ModemManagerSms(sms_obj, received)
            self.callback_obj.mm_modem_sms_state_changed(callback_param)

        """ 
        #print("notify")
        received = messaging.list_sync()
        match = self.objects[modem_obj].match_awaiting_message(received)
        if match != None:
            self.objects[modem_obj].remove_awaiting_message(match.get_object_path())
            print(match.get_object_path(), match.get_number(), match.get_timestamp(), match.get_text())
            #if modem_obj.get_modem().get_state() != ModemManager.ModemState.ENABLING:
            #messaging.delete_sync(match.get_object_path()) #cannot delete SMS: device not yet enabled (8)
            if self.callback_obj != None:
                self.callback_obj.mm_modem_sms_received(modem_obj.get_object_path(), match.get_number(), match.get_timestamp(), match.get_text())
        """

    def on_sms_added(self, messaging, sms_path, received, modem_obj):
        messages = messaging.list_sync()
        sms = self.find_obj_via_path(sms_path, messages)
        state = ModemManager.SmsState.get_string(sms.get_state())
        # received is true when message came from network
        #if (received and state == "receiving") or state == "sending":
        #    print("queue message!")
        sms.connect('notify::state', self.on_sms_state_changed, sms, modem_obj, received)  # queue and emit on state change
        if self.callback_obj != None:
            callback_param = ModemManagerSms(sms, received)
            self.callback_obj.mm_modem_sms_state_changed(callback_param)

    def on_call_added(self, voice, call_path, modem_obj):
        calls = voice.list_calls_sync()
        call_obj = self.find_obj_via_path(call_path, calls)
        call_obj.connect('state_changed',
                     self.on_call_state_changed, call_obj, modem_obj)
        call = ModemManagerCall(call_obj)
        if self.callback_obj != None:
            self.callback_obj.mm_modem_call_added(call)
        # call_obj.accept_sync()
        # call_obj.send_dtmf_sync("123")

    def on_call_state_changed(self, call, old, new, state_reason, call_obj, modem_obj):
        print("on_call_state_changed {} ({} -> {})".format(ModemManager.CallStateReason.get_string(
            state_reason), ModemManager.CallState.get_string(old), ModemManager.CallState.get_string(new)))
        call = ModemManagerCall(call) #state_reason does not equal call.get_state_reason() :X
        call._state = CallState(new)
        call._state_reason = CallStateReason(state_reason)
        if self.callback_obj != None:
            self.callback_obj.mm_modem_call_state_changed(call, CallState(old), CallState(new))

    def on_ussd_notification_changed(self, ussd, network_notification, modem_obj):
        #network_notification is GParamString
        state = Modem3gppUssdSessionState(ussd.get_state())
        notification = ussd.get_network_notification()
        if self.callback_obj != None:
            self.callback_obj.mm_modem_ussd_notification_changed(modem_obj.get_object_path(), state, notification)
            
    def connect_modem_signals(self, modem_info):
        obj = modem_info.obj
        if obj.get_modem() and not modem_info.modem_state_changed_id:
            modem_info.modem_state_changed_id = obj.get_modem().connect('state_changed', self.on_state_notify, obj)
        if obj.get_modem_messaging() and  not modem_info.sms_added_id:
            modem_info.sms_added_id = obj.get_modem_messaging().connect('added', self.on_sms_added, obj)
        if obj.get_modem_voice() and not modem_info.call_added_id:
            modem_info.call_added_id = obj.get_modem_voice().connect(
            'call_added', self.on_call_added, obj)
        if obj.get_modem_3gpp_ussd() and not modem_info.ussd_notification_added:
            modem_info.ussd_notification_added = obj.get_modem_3gpp_ussd().connect("notify::network-notification", self.on_ussd_notification_changed, obj) 

    def add_modem_to_list(self, obj):
        modem_info = ModemInfo(obj)
        self.connect_modem_signals(modem_info)
        self.objects[obj] = modem_info
        if self.callback_obj != None:
            self.callback_obj.mm_modem_added(obj.get_object_path())

    def remove_modem_from_list(self, obj=None):  # when none => remove all modems
        for key, value in list(self.objects.items()):
            if (key == obj or obj == None):
                try:
                    key.get_modem().disconnect(value.modem_state_changed_id)
                except:
                    pass
                try:
                    key.get_modem_messaging().disconnect(value.sms_added_id)
                except:
                    pass
                try:
                    key.get_modem_voice().disconnect(value.call_added_id)
                except:
                    pass
                del self.objects[key]
                if self.callback_obj != None:
                    self.callback_obj.mm_modem_removed(key.get_object_path())

    def get_modem_from_list(self, path):
        if not self.objects:
            raise ValueError("Device list empty")
        if not path:
            #return next(iter(self.objects))
            return list(self.objects.keys())[-1] # get last object, if modem is in failed state and/or added twice we usually wanna grab the latter one
        for key in self.objects.keys():
            if key.get_object_path() == path:
                return key

    def send_at_command(self, command="AT+COPS?", timeout=30, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        return modem_obj.get_modem().command_sync(command, timeout, None)
    
    def change_charset(self, charset="UCS2", timeout=30, modem_path=None):
        command = f'AT+CSCS="{charset}"'
        modem_obj = self.get_modem_from_list(modem_path)
        return modem_obj.get_modem().command_sync(command, timeout, None)

    def change_function_mode(self, function_mode=1, timeout=30, modem_path=None):
        # disalbe modem via modemmanager before setting cfun?
        # bug: when enabling modem with cfun=1 voice does not work afterwards...
        command = f'AT+CFUN={function_mode}'
        modem_obj = self.get_modem_from_list(modem_path)
        return modem_obj.get_modem().command_sync(command, timeout, None)
    
    def disable_rf(self, timeout=30, modem_path=None):
        # disalbe modem via modemmanager before setting cfun?
        # bug: when enabling modem with cfun=1 voice does not work afterwards...
        return self.change_function_mode(function_mode = 4, timeout=timeout, modem_path=modem_path)
    
    def enable_rf(self, timeout=30, modem_path=None):
        return self.change_function_mode(function_mode = 1, timeout=timeout, modem_path=modem_path)

    def send_ussd_code(self, code="*101#", modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        resp = modem_obj.get_modem_3gpp_ussd().initiate_sync(code, None)
        if self.callback_obj != None:
            self.callback_obj.mm_modem_ussd_notification_changed(modem_obj.get_object_path(), modem_obj.get_modem_3gpp_ussd().get_state(), resp)
        return resp

    def send_ussd_response(self, code="1", modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        return modem_obj.get_modem_3gpp_ussd().respond_sync(code, None)
    
    def send_ussd_cancel(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        return modem_obj.get_modem_3gpp_ussd().cancel_sync(None)

    def clear_pdp_context_list(self):
        context_list = self.send_at_command(command="AT+CGDCONT?")
        #context_list = context_list.splitlines()
        context_nums = re.findall('CGDCONT: (.+?),', context_list)
        for n in context_nums:
            # delete pdp context
            at_cmd = f"AT+CGDCONT={n}"
            self.send_at_command(command=at_cmd)

    def register_network(self, network_id, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        gpp = modem_obj.get_modem_3gpp()
        return gpp.register_sync(network_id, None)

    def scan_networks(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        network_list = modem_obj.get_modem_3gpp().scan_sync(None)
        for network in network_list:
            print(network.get_operator_code())

    def call_ping(self, number, ringtime=10, modem_path=None):
        """
        Call a number for some time and stop after that
        """
        modem_obj = self.get_modem_from_list(modem_path)
        args = GLib.Variant('a{sv}', {
            'number': GLib.Variant('s', number)
        })
        call_path = self.create_call(number, modem_path)
        success = self.start_call(call_path)
        time.sleep(ringtime)
        success = self.hangup_call(call_path)
        return True
    
    def create_call(self, number, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        args = GLib.Variant('a{sv}', {
            'number': GLib.Variant('s', number)
        })
        path = modem_obj.get_modem_voice().call_create_call_sync(args, None)
        return path
    
    def find_call(self, call_path, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        calls = modem_obj.get_modem_voice().list_calls_sync()
        call = self.find_obj_via_path(call_path, calls)
        return call
    
    def start_call(self, call_path, modem_path=None):
        call = self.find_call(call_path, modem_path)
        success = call.start_sync()
        return success
    
    def hangup_call(self, call_path, modem_path=None):
        call = self.find_call(call_path, modem_path)
        success = call.hangup_sync()
        return success

    def send_sms(self, number, text, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        props = ModemManager.SmsProperties()
        props.set_number(number)
        props.set_text(text)
        #args = GLib.Variant('a{sv}', {
        #    'number': GLib.Variant('s', number),
        #    'text': GLib.Variant('s', text)
        #})
        sms = modem_obj.get_modem_messaging().create_sync(props, None)
        success = sms.send_sync()
        return success

    def get_state(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        state = modem_obj.get_modem().get_state()
        return ModemManager.ModemState.get_string(state)

    def get_message(self, messaging, message_path):
        #print("searching for: ", message_path)
        received = messaging.list_sync()
        for m in received:
            print(m.get_object_path())
            if m.get_path() == message_path:
                return m
        return None

    def get_message_list(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        messaging = modem_obj.get_modem_messaging()
        ret = []   
        for o in messaging.list_sync():
            ret.append(ModemManagerSms(o))
        return ret

    def delete_message(self, message_path, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        messaging = modem_obj.get_modem_messaging()
        messaging.delete_sync(message_path)

    def wipe_messages(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        messaging = modem_obj.get_modem_messaging()
        for o in messaging.list_sync():
            messaging.delete_sync(o.get_path())

    def get_call_list(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        voice = modem_obj.get_modem_voice()
        ret = []   
        for o in voice.list_calls_sync():
            ret.append(ModemManagerCall(o))
        return ret

    def delete_call(self, call_path, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        voice = modem_obj.get_modem_voice()
        voice.delete_call_sync(call_path)

    def wipe_calls(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        voice = modem_obj.get_modem_voice()
        for o in voice.list_calls_sync():
            voice.delete_call_sync(o.get_path())

    def get_config_for_modem(self, modem_path=None):
        modem_obj = self.get_modem_from_list(modem_path)
        return ModemWatcher.parse_modem_config(modem_obj)

    def register_callback(self, callback_obj):
        self.callback_obj = callback_obj

    def unregister_callback(self):
        self.callback_obj = None

    def is_modem_plugged(self):
        return self.objects


    def get_modem_state(self, modem_path=None):
        try:
            modem_obj = self.get_modem_from_list(modem_path)
            state = ModemState(modem_obj.get_modem().get_state())
            return state
        except ValueError as e: # cannot get modem
            return ModemState.UNKNOWN

    def get_modem_registration_state(self, modem_path=None):
        try:
            modem_obj = self.get_modem_from_list(modem_path)
            modem_3gpp = modem_obj.get_modem_3gpp()
            reg_state = Modem3gppRegistrationState(modem_3gpp.get_registration_state())
            return reg_state
        except ValueError as e: # cannot get modem
            return Modem3gppRegistrationState.UNKNOWN
        
    def get_modem_primary_port(self, modem_path=None):
        try:
            modem_obj = self.get_modem_from_list(modem_path)
            port = modem_obj.get_modem().dup_primary_port()
            return port
        except ValueError as e: # cannot get modem
            return "UNKNOWN"

    def find_obj_via_path(self, path, list):
        for o in list:
            o_path = o.get_object_path()
            if o.get_object_path() == path:
                return o
        raise ValueError("There is no object with the provided path")

    @staticmethod
    def parse_modem_config(modem_obj):
        # modem_obj has this functions: https://valadoc.org/libmm-glib/MM.Object.html
        modem = modem_obj.get_modem()
        modem_3gpp = modem_obj.get_modem_3gpp()
        # advanced signal information (snr und co)
        modem_signal = modem_obj.get_modem_signal()
        modem_location = modem_obj.get_modem_location()

        config = {}
        config['access_technology'] = ModemManager.ModemAccessTechnology.build_string_from_mask(
            modem.get_access_technologies())
        #config['carrier_configuration']  = modem.get_carrier_configuration()
        #config['carrier_configuration_revision']  = modem.get_carrier_configuration_revision()
        #config['current_bands']  = modem.get_current_bands()
        #config['device_identifier']  = modem.get_device_identifier()
        #config['equipment_identifier']  = modem.get_equipment_identifier()
        config['signal_quality'] = modem.get_signal_quality()
        config['numbers'] = modem.dup_own_numbers()

        sim = modem.get_sim_sync()
        if sim != None:
            config['sim_identifier'] = sim.get_identifier()
            config['sim_imsi'] = sim.get_imsi()
            config['sim_operator_identifier'] = sim.get_operator_identifier()
            config['sim_operator_name'] = sim.get_operator_name()

        config['imei'] = modem_3gpp.get_imei()
        config['operator_code'] = modem_3gpp.get_operator_code()
        config['operator_name'] = modem_3gpp.get_operator_name()
        config['pco']  = modem_3gpp.get_pco()

        config['registration_state'] = ModemManager.Modem3gppRegistrationState.get_string(
            modem_3gpp.get_registration_state())

        # https://www.freedesktop.org/software/ModemManager/api/1.0.0/ModemManager-Flags-and-Enumerations.html#MMModemState
        if modem.get_state() >= ModemManager.ModemState.ENABLED:
            location_3gpp = modem_location.get_3gpp_sync()
            if location_3gpp != None:
                config['location_cell_id'] = location_3gpp.get_cell_id()
                config['location_lac'] = location_3gpp.get_location_area_code()
                config['location_mcc'] = location_3gpp.get_mobile_country_code()
                config['location_mnc'] = location_3gpp.get_mobile_network_code()
                config['location_tac'] = location_3gpp.get_tracking_area_code()
        return config
