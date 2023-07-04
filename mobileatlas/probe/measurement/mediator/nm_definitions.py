# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

# enums:
# basically dumped from here:
# https://lazka.github.io/pgi-docs/index.html#NM-1.0/enums.html (accessed 2021-06.14, NM 1.0 (1.30.0))

from mobileatlas.probe.measurement.utils.enum_utils import OrderedEnum

class ActiveConnectionState(OrderedEnum):
    UNKNOWN = 0
    ACTIVATING = 1
    ACTIVATED = 2
    DEACTIVATING = 3
    DEACTIVATED = 4


class ActiveConnectionStateReason(OrderedEnum):
    UNKNOWN = 0
    NONE = 1
    LOGIN_FAILED = 10
    CONNECTION_REMOVED = 11
    DEPENDENCY_FAILED = 12
    DEVICE_REALIZE_FAILED = 13
    DEVICE_REMOVED = 14
    USER_DISCONNECTED = 2
    DEVICE_DISCONNECTED = 3
    SERVICE_STOPPED = 4
    IP_CONFIG_INVALID = 5
    CONNECT_TIMEOUT = 6
    SERVICE_START_TIMEOUT = 7
    SERVICE_START_FAILED = 8
    NO_SECRETS = 9


class AgentManagerError(OrderedEnum):
    FAILED = 0
    PERMISSIONDENIED = 1
    INVALIDIDENTIFIER = 2
    NOTREGISTERED = 3
    NOSECRETS = 4
    USERCANCELED = 5


class Capability(OrderedEnum):
    TEAM = 1
    OVS = 2


class ClientError(OrderedEnum):
    FAILED = 0
    MANAGER_NOT_RUNNING = 1
    OBJECT_CREATION_FAILED = 2


class ClientPermission(OrderedEnum):
    NONE = 0
    ENABLE_DISABLE_NETWORK = 1
    SETTINGS_MODIFY_OWN = 10
    SETTINGS_MODIFY_HOSTNAME = 11
    SETTINGS_MODIFY_GLOBAL_DNS = 12
    RELOAD = 13
    CHECKPOINT_ROLLBACK = 14
    ENABLE_DISABLE_STATISTICS = 15
    ENABLE_DISABLE_CONNECTIVITY_CHECK = 16
    LAST = 17
    WIFI_SCAN = 17
    ENABLE_DISABLE_WIFI = 2
    ENABLE_DISABLE_WWAN = 3
    ENABLE_DISABLE_WIMAX = 4
    SLEEP_WAKE = 5
    NETWORK_CONTROL = 6
    WIFI_SHARE_PROTECTED = 7
    WIFI_SHARE_OPEN = 8
    SETTINGS_MODIFY_SYSTEM = 9


class ClientPermissionResult(OrderedEnum):
    UNKNOWN = 0
    YES = 1
    AUTH = 2
    NO = 3


class ConnectionError(OrderedEnum):
    FAILED = 0
    SETTINGNOTFOUND = 1
    PROPERTYNOTFOUND = 2
    PROPERTYNOTSECRET = 3
    MISSINGSETTING = 4
    INVALIDSETTING = 5
    MISSINGPROPERTY = 6
    INVALIDPROPERTY = 7


class ConnectionMultiConnect(OrderedEnum):
    DEFAULT = 0
    SINGLE = 1
    MANUAL_MULTIPLE = 2
    MULTIPLE = 3


class ConnectivityState(OrderedEnum):
    UNKNOWN = 0
    NONE = 1
    PORTAL = 2
    LIMITED = 3
    FULL = 4


class CryptoError(OrderedEnum):
    FAILED = 0
    INVALID_DATA = 1
    INVALID_PASSWORD = 2
    UNKNOWN_CIPHER = 3
    DECRYPTION_FAILED = 4
    ENCRYPTION_FAILED = 5


class DeviceError(OrderedEnum):
    FAILED = 0
    CREATIONFAILED = 1
    INVALIDARGUMENT = 10
    INVALIDCONNECTION = 2
    INCOMPATIBLECONNECTION = 3
    NOTACTIVE = 4
    NOTSOFTWARE = 5
    NOTALLOWED = 6
    SPECIFICOBJECTNOTFOUND = 7
    VERSIONIDMISMATCH = 8
    MISSINGDEPENDENCIES = 9


class DeviceState(OrderedEnum):
    UNKNOWN = 0
    UNMANAGED = 10
    ACTIVATED = 100
    DEACTIVATING = 110
    FAILED = 120
    UNAVAILABLE = 20
    DISCONNECTED = 30
    PREPARE = 40
    CONFIG = 50
    NEED_AUTH = 60
    IP_CONFIG = 70
    IP_CHECK = 80
    SECONDARIES = 90


class DeviceStateReason(OrderedEnum):
    NONE = 0
    UNKNOWN = 1
    SUPPLICANT_FAILED = 10
    SUPPLICANT_TIMEOUT = 11
    PPP_START_FAILED = 12
    PPP_DISCONNECT = 13
    PPP_FAILED = 14
    DHCP_START_FAILED = 15
    DHCP_ERROR = 16
    DHCP_FAILED = 17
    SHARED_START_FAILED = 18
    SHARED_FAILED = 19
    NOW_MANAGED = 2
    AUTOIP_START_FAILED = 20
    AUTOIP_ERROR = 21
    AUTOIP_FAILED = 22
    MODEM_BUSY = 23
    MODEM_NO_DIAL_TONE = 24
    MODEM_NO_CARRIER = 25
    MODEM_DIAL_TIMEOUT = 26
    MODEM_DIAL_FAILED = 27
    MODEM_INIT_FAILED = 28
    GSM_APN_FAILED = 29
    NOW_UNMANAGED = 3
    GSM_REGISTRATION_NOT_SEARCHING = 30
    GSM_REGISTRATION_DENIED = 31
    GSM_REGISTRATION_TIMEOUT = 32
    GSM_REGISTRATION_FAILED = 33
    GSM_PIN_CHECK_FAILED = 34
    FIRMWARE_MISSING = 35
    REMOVED = 36
    SLEEPING = 37
    CONNECTION_REMOVED = 38
    USER_REQUESTED = 39
    CONFIG_FAILED = 4
    CARRIER = 40
    CONNECTION_ASSUMED = 41
    SUPPLICANT_AVAILABLE = 42
    MODEM_NOT_FOUND = 43
    BT_FAILED = 44
    GSM_SIM_NOT_INSERTED = 45
    GSM_SIM_PIN_REQUIRED = 46
    GSM_SIM_PUK_REQUIRED = 47
    GSM_SIM_WRONG = 48
    INFINIBAND_MODE = 49
    IP_CONFIG_UNAVAILABLE = 5
    DEPENDENCY_FAILED = 50
    BR2684_FAILED = 51
    MODEM_MANAGER_UNAVAILABLE = 52
    SSID_NOT_FOUND = 53
    SECONDARY_CONNECTION_FAILED = 54
    DCB_FCOE_FAILED = 55
    TEAMD_CONTROL_FAILED = 56
    MODEM_FAILED = 57
    MODEM_AVAILABLE = 58
    SIM_PIN_INCORRECT = 59
    IP_CONFIG_EXPIRED = 6
    NEW_ACTIVATION = 60
    PARENT_CHANGED = 61
    PARENT_MANAGED_CHANGED = 62
    OVSDB_FAILED = 63
    IP_ADDRESS_DUPLICATE = 64
    IP_METHOD_UNSUPPORTED = 65
    SRIOV_CONFIGURATION_FAILED = 66
    PEER_NOT_FOUND = 67
    NO_SECRETS = 7
    SUPPLICANT_DISCONNECT = 8
    SUPPLICANT_CONFIG_FAILED = 9


class DeviceType(OrderedEnum):
    UNKNOWN = 0
    ETHERNET = 1
    BOND = 10
    VLAN = 11
    ADSL = 12
    BRIDGE = 13
    GENERIC = 14
    TEAM = 15
    TUN = 16
    IP_TUNNEL = 17
    MACVLAN = 18
    VXLAN = 19
    WIFI = 2
    VETH = 20
    MACSEC = 21
    DUMMY = 22
    PPP = 23
    OVS_INTERFACE = 24
    OVS_PORT = 25
    OVS_BRIDGE = 26
    WPAN = 27
    # 6LOWPAN = 28
    _6LOWPAN = 28
    WIREGUARD = 29
    UNUSED1 = 3
    WIFI_P2P = 30
    VRF = 31
    UNUSED2 = 4
    BT = 5
    OLPC_MESH = 6
    WIMAX = 7
    MODEM = 8
    INFINIBAND = 9


class IPTunnelMode(OrderedEnum):
    UNKNOWN = 0
    IPIP = 1
    GRETAP = 10
    IP6GRETAP = 11
    GRE = 2
    SIT = 3
    ISATAP = 4
    VTI = 5
    IP6IP6 = 6
    IPIP6 = 7
    IP6GRE = 8
    VTI6 = 9


class KeyfileHandlerType(OrderedEnum):
    WARN = 1
    WRITE_CERT = 2


class KeyfileWarnSeverity(OrderedEnum):
    DEBUG = 1000
    INFO = 2000
    INFO_MISSING_FILE = 2901
    WARN = 3000


class ManagerError(OrderedEnum):
    FAILED = 0
    PERMISSIONDENIED = 1
    UNKNOWNLOGLEVEL = 10
    UNKNOWNLOGDOMAIN = 11
    INVALIDARGUMENTS = 12
    MISSINGPLUGIN = 13
    UNKNOWNCONNECTION = 2
    UNKNOWNDEVICE = 3
    CONNECTIONNOTAVAILABLE = 4
    CONNECTIONNOTACTIVE = 5
    CONNECTIONALREADYACTIVE = 6
    DEPENDENCYFAILED = 7
    ALREADYASLEEPORAWAKE = 8
    ALREADYENABLEDORDISABLED = 9


class Metered(OrderedEnum):
    UNKNOWN = 0
    YES = 1
    NO = 2
    GUESS_YES = 3
    GUESS_NO = 4


class RollbackResult(OrderedEnum):
    OK = 0
    ERR_NO_DEVICE = 1
    ERR_DEVICE_UNMANAGED = 2
    ERR_FAILED = 3


class SecretAgentError(OrderedEnum):

    FAILED = 0
    PERMISSIONDENIED = 1
    INVALIDCONNECTION = 2
    USERCANCELED = 3
    AGENTCANCELED = 4
    NOSECRETS = 5


class Setting8021xCKFormat(OrderedEnum):
    UNKNOWN = 0
    X509 = 1
    RAW_KEY = 2
    PKCS12 = 3


class Setting8021xCKScheme(OrderedEnum):
    UNKNOWN = 0
    BLOB = 1
    PATH = 2
    PKCS11 = 3


class SettingCompareFlags(OrderedEnum):
    EXACT = 0
    FUZZY = 1
    IGNORE_TIMESTAMP = 128
    IGNORE_NOT_SAVED_SECRETS = 16
    IGNORE_ID = 2
    DIFF_RESULT_WITH_DEFAULT = 32
    IGNORE_SECRETS = 4
    DIFF_RESULT_NO_DEFAULT = 64
    IGNORE_AGENT_OWNED_SECRETS = 8


class SettingConnectionAutoconnectSlaves(OrderedEnum):
    DEFAULT = -1
    NO = 0
    YES = 1


class SettingConnectionLldp(OrderedEnum):
    DEFAULT = -1
    DISABLE = 0
    ENABLE_RX = 1


class SettingConnectionLlmnr(OrderedEnum):
    DEFAULT = -1
    NO = 0
    RESOLVE = 1
    YES = 2


class SettingConnectionMdns(OrderedEnum):
    DEFAULT = -1
    NO = 0
    RESOLVE = 1
    YES = 2


class SettingDiffResult(OrderedEnum):
    UNKNOWN = 0
    IN_A = 1
    IN_B = 2
    IN_A_DEFAULT = 4
    IN_B_DEFAULT = 8


class SettingIP6ConfigAddrGenMode(OrderedEnum):
    EUI64 = 0
    STABLE_PRIVACY = 1


class SettingIP6ConfigPrivacy(OrderedEnum):
    UNKNOWN = -1
    DISABLED = 0
    PREFER_PUBLIC_ADDR = 1
    PREFER_TEMP_ADDR = 2


class SettingMacRandomization(OrderedEnum):
    DEFAULT = 0
    NEVER = 1
    ALWAYS = 2


class SettingMacsecMode(OrderedEnum):
    PSK = 0
    EAP = 1


class SettingMacsecValidation(OrderedEnum):
    DISABLE = 0
    CHECK = 1
    STRICT = 2


class SettingMacvlanMode(OrderedEnum):
    UNKNOWN = 0
    VEPA = 1
    BRIDGE = 2
    PRIVATE = 3
    PASSTHRU = 4
    SOURCE = 5


class SettingProxyMethod(OrderedEnum):
    NONE = 0
    AUTO = 1


class SettingSerialParity(OrderedEnum):
    NONE = 0
    EVEN = 1
    ODD = 2


class SettingTunMode(OrderedEnum):
    UNKNOWN = 0
    TUN = 1
    TAP = 2


class SettingWirelessPowersave(OrderedEnum):
    DEFAULT = 0
    IGNORE = 1
    DISABLE = 2
    ENABLE = 3


class SettingWirelessSecurityFils(OrderedEnum):
    DEFAULT = 0
    DISABLE = 1
    OPTIONAL = 2
    REQUIRED = 3


class SettingWirelessSecurityPmf(OrderedEnum):
    DEFAULT = 0
    DISABLE = 1
    OPTIONAL = 2
    REQUIRED = 3


class SettingsError(OrderedEnum):
    FAILED = 0
    PERMISSIONDENIED = 1
    NOTSUPPORTED = 2
    INVALIDCONNECTION = 3
    READONLYCONNECTION = 4
    UUIDEXISTS = 5
    INVALIDHOSTNAME = 6
    INVALIDARGUMENTS = 7


class SriovVFVlanProtocol(OrderedEnum):
    #1Q = 0
    _1Q = 0
    #1AD = 1
    _1AD = 1


class State(OrderedEnum):
    UNKNOWN = 0
    ASLEEP = 10
    DISCONNECTED = 20
    DISCONNECTING = 30
    CONNECTING = 40
    CONNECTED_LOCAL = 50
    CONNECTED_SITE = 60
    CONNECTED_GLOBAL = 70


class Ternary(OrderedEnum):
    DEFAULT = -1
    FALSE = 0
    TRUE = 1


class UtilsSecurityType(OrderedEnum):
    INVALID = 0
    NONE = 1
    OWE = 10
    WPA3_SUITE_B_192 = 11
    STATIC_WEP = 2
    LEAP = 3
    DYNAMIC_WEP = 4
    WPA_PSK = 5
    WPA_ENTERPRISE = 6
    WPA2_PSK = 7
    WPA2_ENTERPRISE = 8
    SAE = 9


class VlanPriorityMap(OrderedEnum):
    INGRESS_MAP = 0
    EGRESS_MAP = 1


class VpnConnectionState(OrderedEnum):
    UNKNOWN = 0
    PREPARE = 1
    NEED_AUTH = 2
    CONNECT = 3
    IP_CONFIG_GET = 4
    ACTIVATED = 5
    FAILED = 6
    DISCONNECTED = 7


class VpnConnectionStateReason(OrderedEnum):
    UNKNOWN = 0
    NONE = 1
    LOGIN_FAILED = 10
    CONNECTION_REMOVED = 11
    USER_DISCONNECTED = 2
    DEVICE_DISCONNECTED = 3
    SERVICE_STOPPED = 4
    IP_CONFIG_INVALID = 5
    CONNECT_TIMEOUT = 6
    SERVICE_START_TIMEOUT = 7
    SERVICE_START_FAILED = 8
    NO_SECRETS = 9


class VpnPluginError(OrderedEnum):
    FAILED = 0
    STARTINGINPROGRESS = 1
    ALREADYSTARTED = 2
    STOPPINGINPROGRESS = 3
    ALREADYSTOPPED = 4
    WRONGSTATE = 5
    BADARGUMENTS = 6
    LAUNCHFAILED = 7
    INVALIDCONNECTION = 8
    INTERACTIVENOTSUPPORTED = 9


class VpnPluginFailure(OrderedEnum):
    LOGIN_FAILED = 0
    CONNECT_FAILED = 1
    BAD_IP_CONFIG = 2


class VpnServiceState(OrderedEnum):
    UNKNOWN = 0
    INIT = 1
    SHUTDOWN = 2
    STARTING = 3
    STARTED = 4
    STOPPING = 5
    STOPPED = 6


class WepKeyType(OrderedEnum):
    UNKNOWN = 0
    KEY = 1
    PASSPHRASE = 2


class WimaxNspNetworkType(OrderedEnum):
    UNKNOWN = 0
    HOME = 1
    PARTNER = 2
    ROAMING_PARTNER = 3



if __name__ == "__main__":
    import requests
    from bs4 import BeautifulSoup
    resp = requests.get("https://lazka.github.io/pgi-docs/NM-1.0/enums.html")
    soup = BeautifulSoup(resp.content, "html.parser")
    #print(resp.content)
    elem = soup.find(id="details")
    for e in elem.find_all(name="dt"):
        id = e.get("id", None)
        if id is not None:
            keypath = id.split(".")
            name = keypath[-1]
            if len(keypath) <= 2:
                print(f"\nclass {name}(OrderedEnum):")
            else:
                values = e.find_all("em",)
                for v in values:
                    print(f"\t{name}{v.text}")
                    
    #classes = elem.find_all(name="dl", attrs={"class":"class"})
    #for c in classes:
    #    class_name = c.find_all('dt')   #id=NM.*
    #    #class_name = c.find_all(name="code", attrs={"class":"descname"}, recursive = True)
    #    #content = c.find_all('dd')
    #    attribute = elem.find_all(name="dl", attrs={"class":"attribute"})
    #    for a in attribute:
    #        a.find_all(name="code", attrs={"class":"descname"})