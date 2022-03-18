#!/usr/bin/env python3

from mobileatlas.probe.measurement.mediator.nm_definitions import DeviceState, DeviceStateReason
import uuid

import gi

gi.require_version('NM', '1.0')
from gi.repository import NM


class NMCallbackClass:
    def nm_modem_added(self, udi):
        raise NotImplementedError("method not implemented")

    def nm_modem_removed(self, udi):
        raise NotImplementedError("method not implemented")

    def nm_modem_state_changed(self, udi, old_state: DeviceState, new_state: DeviceState, reason: DeviceStateReason):
        raise NotImplementedError("method not implemented")
    
    # TODO: maybe add callbacks for activeconnection?


class DeviceInfo:
    def __init__(self, device, device_state_changed_id):
        self.device = device
        self.device_state_changed_id = device_state_changed_id


"""
The NetworkWatcher class is responsible for monitoring NetworkManager
"""


class NetworkWatcher:
    """
    Constructor
    """
    def __init__(self, callback=None):
        self.client = NM.Client.new()
        self.callback_obj = callback
        self.devices = dict()

        # initially add all present devices
        for dev in self.client.get_devices():
            self.device_added(self.client, dev)

        self.client.connect('device_added', self.device_added)
        self.client.connect('device_removed', self.device_removed)

    def device_added(self, client, device):
        if(device.get_device_type() == NM.DeviceType.MODEM):
            # print("device_added")
            self.add_device_to_list(device)

    def device_removed(self, client, device):
        if(device.get_device_type() == NM.DeviceType.MODEM):
            # print("device_removed")
            self.remove_device_from_list(device)

    def add_device_to_list(self, device):
        state_id = device.connect('state_changed', self.on_state_notify)
        self.devices[device] = DeviceInfo(device, state_id)
        if self.callback_obj != None:
            self.callback_obj.nm_modem_added(device.get_udi())

    # when none => remove all modems
    def remove_device_from_list(self, device=None):
        for key, value in list(self.devices.items()):
            if (key == device or device == None):
                # key.disconnect(value.device_state_changed_id) #TypeError: argument cancellable: Expected Gio.Cancellable, but got int
                del self.devices[key]
                if self.callback_obj != None:
                    self.callback_obj.nm_modem_removed(key.get_udi())

    def get_device_from_list(self, udi):
        if not self.devices:
            raise ValueError("Device list empty")
        if not udi:
            return next(iter(self.devices))
        for key in self.devices.keys():
            if key.get_udi() == udi:
                return key

    def get_connection_for_device(self, device, con_id):
        possible_connections = device.get_available_connections()
        for con in possible_connections:
            if con.get_id() == con_id:
                return con
        raise ValueError("Connection not found")

    def create_connection(self, name, apn=None, username=None, password=None, network_id=None, udi=None):
        con = NM.SimpleConnection.new()
        s_con = NM.SettingConnection.new()
        s_con.props.id = name
        s_con.props.uuid = str(uuid.uuid4())
        s_con.props.type = "gsm"
        s_con.props.autoconnect = False

        s_gsm = NM.SettingGsm.new()
        s_gsm.props.number = "*99#"
        s_gsm.props.apn = apn
        s_gsm.props.username = username
        s_gsm.props.password = password
        s_gsm.props.network_id = network_id

        s_ser = NM.SettingSerial.new()
        s_ser.props.baud = 115200

        s_ip4 = NM.SettingIP4Config.new()
        s_ip4.props.method = "auto"

        s_ip6 = NM.SettingIP6Config.new()
        s_ip6.props.method = "auto" #"ignore"

        # print(s_con.to_string())

        con.add_setting(s_con)
        con.add_setting(s_gsm)
        con.add_setting(s_ser)
        con.add_setting(s_ip4)
        con.add_setting(s_ip6)

        # print(con.dump())

        #device = self.get_device_from_list(udi)
        #template = self.get_connection_for_device(device, "template")
        # print(template.dump())

        return con

        con.replace_setting(NM.SettingGsm.new())
        gsm = con.get_setting_gsm()
        gsm.apn = apn
        con.add_setting(gsm)
        # print(con.dump())
        # print(con.get_setting_gsm().apn)
        #print(con.commit_changes(True, None))

        # print(con.get_unsaved())
        return con

    def send_connect_device(self, con_id, udi=None):
        device = self.get_device_from_list(udi)
        con = self.get_connection_for_device(device, con_id)
        return self.client.activate_connection_async(con, device, None, None, None)

    def get_config_for_device(self, udi=None):
        device = self.get_device_from_list(udi)
        return NetworkWatcher.parse_device_config(device)

    def connect_device(self, connection, udi=None):
        device = self.get_device_from_list(udi)
        #props = device.list_properties()
        # print(props)
        # for p in device.props:
        #    print(p)
        return self.client.add_and_activate_connection_async(connection, device, None, None, None)

    # def callback_connect(self, client, async_result):
    #    src = async_result.get_source_object()
    #    usr_data = async_result.get_user_data()

    def disconnect(self, udi=None):
        device = self.get_device_from_list(udi)
        device.disconnect()

    def on_state_notify(self, device, new_state, old_state, reason):
        #print('device state changed: %s' % new_state_str)
        if self.callback_obj != None:
            self.callback_obj.nm_modem_state_changed(
                device.get_udi(), DeviceState(old_state), DeviceState(new_state), DeviceStateReason(reason))
        # if(new_state_str == "NM_DEVICE_STATE_DISCONNECTED"):
        #    self.send_connect_device("T-Mobile gprsinternet", device.get_udi())

    
    def get_modem_state(self, udi=None):
        device = self.get_device_from_list(udi)
        state = DeviceState(device.get_state())
        return  state

    def register_callback(self, callback_obj):
        self.callback_obj = callback_obj

    def unregister_callback(self):
        self.callback_obj = None


    @staticmethod
    def parse_ip6_addresses_config(ip6_addresses):
        if ip6_addresses is not None:
            config = []
            for addr in ip6_addresses:
                elem = {}
                elem['address'] = addr.get_address()
                elem['family'] = addr.get_family()
                elem['prefix'] = addr.get_prefix()
                config.append(elem)
            return config
        return None

    @staticmethod
    def parse_routes_config(ip_routes):
        if ip_routes is not None:
            config = []
            for addr in ip_routes:
                elem = {}
                elem['dest'] = addr.get_dest()
                elem['metric'] = addr.get_metric()
                elem['next_hop'] = addr.get_next_hop()
                elem['prefix'] = addr.get_prefix()
                config.append(elem)
            return config
        return None

    @staticmethod
    def parse_ip4_addresses_config(ip4_addresses):
        if ip4_addresses is not None:
            config = []
            # for i in range(ip4_addresses.__len__()):
            for addr in ip4_addresses:
                elem = {}
                elem['address'] = addr.get_address()
                elem['prefix'] = addr.get_prefix()
                elem['family'] = addr.get_family()
                config.append(elem)
            return config
        return None

    @staticmethod
    def parse_ip4_config(ip4):
        if ip4 is not None:
            config = {}
            config['addresses'] = NetworkWatcher.parse_ip4_addresses_config(ip4.get_addresses())
            config['domains'] = ip4.get_domains()
            config['gateway'] = ip4.get_gateway()
            config['nameserver'] = ip4.get_nameservers()
            config['routes'] = NetworkWatcher.parse_routes_config(ip4.get_routes())
            config['searches'] = ip4.get_searches()
            config['wins_server'] = ip4.get_wins_servers()
            return config
        return None

    @staticmethod
    def parse_ip6_config(ip6):
        if ip6 is not None:
            config = {}
            config['addresses'] = NetworkWatcher.parse_ip6_addresses_config(ip6.get_addresses())
            config['domains'] = ip6.get_domains()
            config['gateway'] = ip6.get_gateway()
            config['nameserver'] = ip6.get_nameservers()
            #config['nameserver'] = []
            #for i in range(ip6.get_num_nameservers()):
            #    config['nameserver'].append(ip6.get_nameserver(i))
            config['routes'] = NetworkWatcher.parse_routes_config(ip6.get_routes())
            config['searches'] = ip6.get_searches()
            return config
        return None

    #TODO: convert to current logger to device class: https://lazka.github.io/pgi-docs/index.html#NM-1.0/classes/Device.html#NM.Device
    @staticmethod
    def parse_device_config(device):
        config = {}
        config['description'] = device.get_description()
        config['driver'] = device.get_driver()
        config['driver_version'] = device.get_driver_version()
        config['firmware_version'] = device.get_firmware_version()
        config['hw_address'] = device.get_hw_address()
        config['iface'] = device.get_iface()
        config['ip4'] = NetworkWatcher.parse_ip4_config(device.get_ip4_config())
        config['ip6'] = NetworkWatcher.parse_ip6_config(device.get_ip6_config())
        config['ip_iface'] = device.get_ip_iface()
        config['dhcp4'] = device.get_dhcp4_config()
        config['dhcp6'] = device.get_dhcp6_config()
        config['mtu'] = device.get_mtu()
        config['physical_port_id'] = device.get_physical_port_id()
        config['product'] = device.get_product()
        # config['udi'] = device.get_udi()
        config['vendor'] = device.get_vendor()
        return config



# https://kite.com/python/examples/4023/threading-wait-for-either-of-two-events-to-be-set


# device_added
# device state changed: NM_DEVICE_STATE_UNAVAILABLE
# device state changed: NM_DEVICE_STATE_DISCONNECTED
# device state changed: NM_DEVICE_STATE_NEED_AUTH
# device state changed: NM_DEVICE_STATE_PREPARE
# device state changed: NM_DEVICE_STATE_CONFIG
# device state changed: NM_DEVICE_STATE_IP_CONFIG
# device state changed: NM_DEVICE_STATE_IP_CHECK
# device state changed: NM_DEVICE_STATE_SECONDARIES
# device state changed: NM_DEVICE_STATE_ACTIVATED

"""
mm_modem_added /org/freedesktop/ModemManager1/Modem/66
nm_modem_added /org/freedesktop/ModemManager1/Modem/66
mm_modem_removed /org/freedesktop/ModemManager1/Modem/66
nm_modem_removed /org/freedesktop/ModemManager1/Modem/66
mm_modem_added /org/freedesktop/ModemManager1/Modem/67
nm_modem_added /org/freedesktop/ModemManager1/Modem/67
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/67: NM_DEVICE_STATE_UNKNOWN -> NM_DEVICE_STATE_UNAVAILABLE
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/67: NM_DEVICE_STATE_UNAVAILABLE -> NM_DEVICE_STATE_DISCONNECTED
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/67: disabled -> enabling
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/67: enabling -> searching
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/67: searching -> registered
mm_modem_removed /org/freedesktop/ModemManager1/Modem/67
nm_modem_removed /org/freedesktop/ModemManager1/Modem/67

mm_modem_added /org/freedesktop/ModemManager1/Modem/68
nm_modem_added /org/freedesktop/ModemManager1/Modem/68
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_UNKNOWN -> NM_DEVICE_STATE_UNAVAILABLE
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_UNAVAILABLE -> NM_DEVICE_STATE_DISCONNECTED
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: disabled -> enabling
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: enabling -> registered


nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_DISCONNECTED -> NM_DEVICE_STATE_NEED_AUTH
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_NEED_AUTH -> NM_DEVICE_STATE_PREPARE
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: registered -> connecting
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: connecting -> connected
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_PREPARE -> NM_DEVICE_STATE_CONFIG
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_CONFIG -> NM_DEVICE_STATE_IP_CONFIG
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_IP_CONFIG -> NM_DEVICE_STATE_IP_CHECK
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_IP_CHECK -> NM_DEVICE_STATE_SECONDARIES
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_SECONDARIES -> NM_DEVICE_STATE_ACTIVATED

nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_ACTIVATED -> NM_DEVICE_STATE_DEACTIVATING
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: connected -> disconnecting
mm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: disconnecting -> registered
nm_modem_state_changed /org/freedesktop/ModemManager1/Modem/68: NM_DEVICE_STATE_DEACTIVATING -> NM_DEVICE_STATE_DISCONNECTED
"""
