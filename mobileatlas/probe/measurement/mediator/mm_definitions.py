#!/usr/bin/env python3

from mobileatlas.probe.measurement.utils.enum_utils import OrderedEnum
from mobileatlas.probe.measurement.utils.serialize_utils import object_dict

class ModemManagerCall:
    def __init__(self, call_obj):
        self._path: str = call_obj.get_path()
        self._state: CallState = CallState(call_obj.get_state())
        self._state_reason: CallStateReason = CallStateReason(call_obj.get_state_reason())
        self._direction: CallDirection = CallDirection(call_obj.get_direction())
        self._number: str = call_obj.get_number()
        self._multiparty: bool = call_obj.get_multiparty()
        self._audio_port: str = call_obj.get_audio_port()
        self._audio_format: CallAudioFormat = CallAudioFormat(call_obj.get_audio_format())

class CallAudioFormat:
    def __init__(self, audio_format_obj):
        self._encoding: str = audio_format_obj.get_encoding()
        self._rate: int =  audio_format_obj.get_rate()
        self._resolution: str =  audio_format_obj.get_resolution()

class ModemManagerSms:
    def __init__(self, sms_obj, received = False):
        self._path: str = sms_obj.get_path()
        self._state: SmsState = SmsState(sms_obj.get_state())
        self._pdu_type: SmsPduType = SmsPduType(sms_obj.get_pdu_type())
        self._number: str = sms_obj.get_number()
        self._text: str = sms_obj.get_text()
        self._data: bytes = sms_obj.get_data().hex()    #convert to hex since serialized byte array is crap when serialized to json
        self._smsc: str = sms_obj.get_smsc()
        self._validity_type: SmsValidityType = SmsValidityType(sms_obj.get_validity_type())
        self._validity_relative: int = sms_obj.get_validity_relative()
        self._class: int = sms_obj.get_class()
        self._teleservice_id: SmsCdmaTeleserviceId = SmsCdmaTeleserviceId(sms_obj.get_teleservice_id())
        self._service_category: SmsCdmaServiceCategory = SmsCdmaServiceCategory(sms_obj.get_service_category())
        self._delivery_report_request: bool = sms_obj.get_delivery_report_request()
        self._message_reference: int = sms_obj.get_message_reference()
        self._timestamp: str = sms_obj.get_timestamp()
        self._discharge_timestamp: str = sms_obj.get_discharge_timestamp()
        self._delivery_state: SmsDeliveryState = SmsDeliveryState(sms_obj.get_delivery_state())
        self._storage: SmsStorage = SmsStorage(sms_obj.get_storage())
        self._received: bool = received #on_sms_added param, is true when sms came from network; not sure if there is any difference to "pdu_type == SmsPduType.DELIVER"

    def get_path(self):
        return self._path

    def get_state(self):
        return self._state

    def get_pdu_type(self):
        return self._pdu_type

    def get_number(self):
        return self._number

    def get_text(self):
        return self._text

    def get_data(self):
        return self._data
    
    def get_smsc(self):
        return self._smsc

    def get_validity_type(self):
        return self._validity_relative
    
    def get_validity_relative(self):
        return self.get_validity_relative

    def get_class(self):
        return self._class

    def get_teleservice_id(self):
        return self._teleservice_id

    def get_service_category(self):
        return self._service_category

    def get_delivery_report_request(self):
        self._delivery_report_request

    def get_message_reference(self):
        return self._message_reference
    
    def get_timestamp(self):
        return self._timestamp
    
    def get_discharge_timestamp(self):
        return self._discharge_timestamp
    
    def get_delivery_state(self):
        return self._delivery_state
    
    def get_storage(self):
        return self._storage

    def to_dict(self):
        return object_dict(self)

# enums:
# basically dumped from here:
# https://lazka.github.io/pgi-docs/#ModemManager-1.0/enums.html (accessed 2021-06.14, ModemManager 1.0 (1.14.12))
class BearerIpMethod(OrderedEnum):
    UNKNOWN = 0
    PPP = 1
    STATIC = 2
    DHCP = 3
    
class BearerType(OrderedEnum):
    UNKNOWN = 0
    DEFAULT = 1
    DEFAULT_ATTACH = 2
    DEDICATED = 3

class CallDirection(OrderedEnum):
    UNKNOWN = 0
    INCOMING = 1
    OUTGOING = 2

class CallState(OrderedEnum):
    UNKNOWN = 0
    DIALING = 1
    RINGING_OUT = 2
    RINGING_IN = 3
    ACTIVE = 4
    HELD = 5
    WAITING = 6
    TERMINATED = 7

class CallStateReason(OrderedEnum):
    UNKNOWN = 0
    OUTGOING_STARTED = 1
    INCOMING_NEW = 2
    ACCEPTED = 3
    TERMINATED = 4
    REFUSED_OR_BUSY = 5
    ERROR = 6
    AUDIO_SETUP_FAILED = 7
    TRANSFERRED = 8
    DEFLECTED = 9

class CdmaActivationError(OrderedEnum):
    NONE = 0
    UNKNOWN = 1
    ROAMING = 2
    WRONGRADIOINTERFACE = 3
    COULDNOTCONNECT = 4
    SECURITYAUTHENTICATIONFAILED = 5
    PROVISIONINGFAILED = 6
    NOSIGNAL = 7
    TIMEDOUT = 8
    STARTFAILED = 9

class ConnectionError(OrderedEnum):
    UNKNOWN = 0
    NOCARRIER = 1
    NODIALTONE = 2
    BUSY = 3
    NOANSWER = 4

class CoreError(OrderedEnum):
    FAILED = 0
    CANCELLED = 1
    TOOMANY = 10
    NOTFOUND = 11
    RETRY = 12
    EXISTS = 13
    ABORTED = 2
    UNSUPPORTED = 3
    NOPLUGINS = 4
    UNAUTHORIZED = 5
    INVALIDARGS = 6
    INPROGRESS = 7
    WRONGSTATE = 8
    CONNECTED = 9

class FirmwareImageType(OrderedEnum):
    UNKNOWN = 0
    GENERIC = 1
    GOBI = 2

class SmsPduType(OrderedEnum):
    UNKNOWN = 0
    DELIVER = 1
    SUBMIT = 2
    STATUS_REPORT = 3
    CDMA_DELIVER = 32
    CDMA_SUBMIT = 33
    CDMA_CANCELLATION = 34
    CDMA_DELIVERY_ACKNOWLEDGEMENT = 35
    CDMA_USER_ACKNOWLEDGEMENT = 36
    CDMA_READ_ACKNOWLEDGEMENT = 37

class MessageError(OrderedEnum):
    MEFAILURE = 300
    SMSSERVICERESERVED = 301
    NOTALLOWED = 302
    NOTSUPPORTED = 303
    INVALIDPDUPARAMETER = 304
    INVALIDTEXTPARAMETER = 305
    SIMNOTINSERTED = 310
    SIMPIN = 311
    PHSIMPIN = 312
    SIMFAILURE = 313
    SIMBUSY = 314
    SIMWRONG = 315
    SIMPUK = 316
    SIMPIN2 = 317
    SIMPUK2 = 318
    MEMORYFAILURE = 320
    INVALIDINDEX = 321
    MEMORYFULL = 322
    SMSCADDRESSUNKNOWN = 330
    NONETWORK = 331
    NETWORKTIMEOUT = 332
    NOCNMAACKEXPECTED = 340
    UNKNOWN = 500

class MobileEquipmentError(OrderedEnum):
    PHONEFAILURE = 0
    NOCONNECTION = 1
    SIMNOTINSERTED = 10
    UNKNOWN = 100
    GPRSIMSIUNKNOWNINHLR = 102
    GPRSILLEGALMS = 103
    GPRSIMSIUNKNOWNINVLR = 104
    GPRSILLEGALME = 106
    GPRSSERVICENOTALLOWED = 107
    GPRSANDNONGPRSSERVICESNOTALLOWED = 108
    SIMPIN = 11
    GPRSPLMNNOTALLOWED = 111
    GPRSLOCATIONNOTALLOWED = 112
    GPRSROMAINGNOTALLOWED = 113
    GPRSNOCELLSINLOCATIONAREA = 115
    GPRSNETWORKFAILURE = 117
    SIMPUK = 12
    GPRSCONGESTION = 122
    NOTAUTHORIZEDFORCSG = 125
    GPRSINSUFFICIENTRESOURCES = 126
    GPRSMISSINGORUNKNOWNAPN = 127
    GPRSUNKNOWNPDPADDRESSORTYPE = 128
    GPRSUSERAUTHENTICATIONFAILED = 129
    SIMFAILURE = 13
    GPRSACTIVATIONREJECTEDBYGGSNORGW = 130
    GPRSACTIVATIONREJECTEDUNSPECIFIED = 131
    GPRSSERVICEOPTIONNOTSUPPORTED = 132
    GPRSSERVICEOPTIONNOTSUBSCRIBED = 133
    GPRSSERVICEOPTIONOUTOFORDER = 134
    SIMBUSY = 14
    GPRSFEATURENOTSUPPORTED = 140
    GPRSSEMANTICERRORINTFTOPERATION = 141
    GPRSSYNTACTICALERRORINTFTOPERATION = 142
    GPRSUNKNOWNPDPCONTEXT = 143
    GPRSSEMANTICERRORSINPACKETFILTER = 144
    GPRSSYNTACTICALERRORSINPACKETFILTER = 145
    GPRSPDPCONTEXTWITHOUTTFTALREADYACTIVATED = 146
    GPRSUNKNOWN = 148
    GPRSPDPAUTHFAILURE = 149
    SIMWRONG = 15
    GPRSINVALIDMOBILECLASS = 150
    GPRSLASTPDNDISCONNECTIONNOTALLOWEDLEGACY = 151
    INCORRECTPASSWORD = 16
    SIMPIN2 = 17
    GPRSLASTPDNDISCONNECTIONNOTALLOWED = 171
    GPRSSEMANTICALLYINCORRECTMESSAGE = 172
    GPRSMANDATORYIEERROR = 173
    GPRSIENOTIMPLEMENTED = 174
    GPRSCONDITIONALIEERROR = 175
    GPRSUNSPECIFIEDPROTOCOLERROR = 176
    GPRSOPERATORDETERMINEDBARRING = 177
    GPRSMAXIMUMNUMBEROFPDPCONTEXTSREACHED = 178
    GPRSREQUESTEDAPNNOTSUPPORTED = 179
    SIMPUK2 = 18
    GPRSREQUESTREJECTEDBCMVIOLATION = 180
    LINKRESERVED = 2
    MEMORYFULL = 20
    INVALIDINDEX = 21
    NOTFOUND = 22
    MEMORYFAILURE = 23
    TEXTTOOLONG = 24
    INVALIDCHARS = 25
    DIALSTRINGTOOLONG = 26
    DIALSTRINGINVALID = 27
    NOTALLOWED = 3
    NONETWORK = 30
    NETWORKTIMEOUT = 31
    NETWORKNOTALLOWED = 32
    NOTSUPPORTED = 4
    NETWORKPIN = 40
    NETWORKPUK = 41
    NETWORKSUBSETPIN = 42
    NETWORKSUBSETPUK = 43
    SERVICEPIN = 44
    SERVICEPUK = 45
    CORPPIN = 46
    CORPPUK = 47
    HIDDENKEYREQUIRED = 48
    EAPMETHODNOTSUPPORTED = 49
    PHSIMPIN = 5
    INCORRECTPARAMETERS = 50
    PHFSIMPIN = 6
    PHFSIMPUK = 7

class Modem3gppEpsUeModeOperation(OrderedEnum):
    UNKNOWN = 0
    PS_1 = 1
    PS_2 = 2
    CSPS_1 = 3
    CSPS_2 = 4

class Modem3gppNetworkAvailability(OrderedEnum):
    UNKNOWN = 0
    AVAILABLE = 1
    CURRENT = 2
    FORBIDDEN = 3

class Modem3gppRegistrationState(OrderedEnum):
    IDLE = 0
    HOME = 1
    ROAMING_CSFB_NOT_PREFERRED = 10
    ATTACHED_RLOS = 11
    SEARCHING = 2
    DENIED = 3
    UNKNOWN = 4
    ROAMING = 5
    HOME_SMS_ONLY = 6
    ROAMING_SMS_ONLY = 7
    EMERGENCY_ONLY = 8
    HOME_CSFB_NOT_PREFERRED = 9

class Modem3gppSubscriptionState(OrderedEnum):
    UNKNOWN = 0
    UNPROVISIONED = 1
    PROVISIONED = 2
    OUT_OF_DATA = 3

class Modem3gppUssdSessionState(OrderedEnum):
    UNKNOWN = 0
    IDLE = 1
    ACTIVE = 2
    USER_RESPONSE = 3

class ModemBand(OrderedEnum):
    UNKNOWN = 0
    EGSM = 1
    UTRAN_8 = 10
    EUTRAN_70 = 100
    EUTRAN_71 = 101
    UTRAN_9 = 11
    UTRAN_2 = 12
    CDMA_BC0 = 128
    CDMA_BC1 = 129
    UTRAN_7 = 13
    CDMA_BC2 = 130
    CDMA_BC3 = 131
    CDMA_BC4 = 132
    CDMA_BC5 = 134
    CDMA_BC6 = 135
    CDMA_BC7 = 136
    CDMA_BC8 = 137
    CDMA_BC9 = 138
    CDMA_BC10 = 139
    G450 = 14
    CDMA_BC11 = 140
    CDMA_BC12 = 141
    CDMA_BC13 = 142
    CDMA_BC14 = 143
    CDMA_BC15 = 144
    CDMA_BC16 = 145
    CDMA_BC17 = 146
    CDMA_BC18 = 147
    CDMA_BC19 = 148
    G480 = 15
    G750 = 16
    G380 = 17
    G410 = 18
    G710 = 19
    DCS = 2
    G810 = 20
    UTRAN_10 = 210
    UTRAN_11 = 211
    UTRAN_12 = 212
    UTRAN_13 = 213
    UTRAN_14 = 214
    UTRAN_19 = 219
    UTRAN_20 = 220
    UTRAN_21 = 221
    UTRAN_22 = 222
    UTRAN_25 = 225
    UTRAN_26 = 226
    UTRAN_32 = 232
    ANY = 256
    PCS = 3
    EUTRAN_1 = 31
    EUTRAN_2 = 32
    EUTRAN_3 = 33
    EUTRAN_4 = 34
    EUTRAN_5 = 35
    EUTRAN_6 = 36
    EUTRAN_7 = 37
    EUTRAN_8 = 38
    EUTRAN_9 = 39
    G850 = 4
    EUTRAN_10 = 40
    EUTRAN_11 = 41
    EUTRAN_12 = 42
    EUTRAN_13 = 43
    EUTRAN_14 = 44
    EUTRAN_17 = 47
    EUTRAN_18 = 48
    EUTRAN_19 = 49
    UTRAN_1 = 5
    EUTRAN_20 = 50
    EUTRAN_21 = 51
    EUTRAN_22 = 52
    EUTRAN_23 = 53
    EUTRAN_24 = 54
    EUTRAN_25 = 55
    EUTRAN_26 = 56
    EUTRAN_27 = 57
    EUTRAN_28 = 58
    EUTRAN_29 = 59
    UTRAN_3 = 6
    EUTRAN_30 = 60
    EUTRAN_31 = 61
    EUTRAN_32 = 62
    EUTRAN_33 = 63
    EUTRAN_34 = 64
    EUTRAN_35 = 65
    EUTRAN_36 = 66
    EUTRAN_37 = 67
    EUTRAN_38 = 68
    EUTRAN_39 = 69
    UTRAN_4 = 7
    EUTRAN_40 = 70
    EUTRAN_41 = 71
    EUTRAN_42 = 72
    EUTRAN_43 = 73
    EUTRAN_44 = 74
    EUTRAN_45 = 75
    EUTRAN_46 = 76
    EUTRAN_47 = 77
    EUTRAN_48 = 78
    EUTRAN_49 = 79
    UTRAN_6 = 8
    EUTRAN_50 = 80
    EUTRAN_51 = 81
    EUTRAN_52 = 82
    EUTRAN_53 = 83
    EUTRAN_54 = 84
    EUTRAN_55 = 85
    EUTRAN_56 = 86
    EUTRAN_57 = 87
    EUTRAN_58 = 88
    EUTRAN_59 = 89
    UTRAN_5 = 9
    EUTRAN_60 = 90
    EUTRAN_61 = 91
    EUTRAN_62 = 92
    EUTRAN_63 = 93
    EUTRAN_64 = 94
    EUTRAN_65 = 95
    EUTRAN_66 = 96
    EUTRAN_67 = 97
    EUTRAN_68 = 98
    EUTRAN_69 = 99

class ModemCdmaActivationState(OrderedEnum):
    UNKNOWN = 0
    NOT_ACTIVATED = 1
    ACTIVATING = 2
    PARTIALLY_ACTIVATED = 3
    ACTIVATED = 4

class ModemCdmaRegistrationState(OrderedEnum):
    UNKNOWN = 0
    REGISTERED = 1
    HOME = 2
    ROAMING = 3

class ModemCdmaRmProtocol(OrderedEnum):
    UNKNOWN = 0
    ASYNC = 1
    PACKET_RELAY = 2
    PACKET_NETWORK_PPP = 3
    PACKET_NETWORK_SLIP = 4
    STU_III = 5

class ModemContactsStorage(OrderedEnum):
    UNKNOWN = 0
    ME = 1
    SM = 2
    MT = 3

class ModemLock(OrderedEnum):
    UNKNOWN = 0
    NONE = 1
    PH_SIM_PIN = 10
    PH_CORP_PIN = 11
    PH_CORP_PUK = 12
    PH_FSIM_PIN = 13
    PH_FSIM_PUK = 14
    PH_NETSUB_PIN = 15
    PH_NETSUB_PUK = 16
    SIM_PIN = 2
    SIM_PIN2 = 3
    SIM_PUK = 4
    SIM_PUK2 = 5
    PH_SP_PIN = 6
    PH_SP_PUK = 7
    PH_NET_PIN = 8
    PH_NET_PUK = 9

class ModemPortType(OrderedEnum):
    UNKNOWN = 1
    NET = 2
    AT = 3
    QCDM = 4
    GPS = 5
    QMI = 6
    MBIM = 7
    AUDIO = 8    

class ModemPowerState(OrderedEnum):
    UNKNOWN = 0
    OFF = 1
    LOW = 2
    ON = 3

class ModemState(OrderedEnum):
    FAILED = -1
    UNKNOWN = 0
    INITIALIZING = 1
    CONNECTING = 10
    CONNECTED = 11
    LOCKED = 2
    DISABLED = 3
    DISABLING = 4
    ENABLING = 5
    ENABLED = 6
    SEARCHING = 7
    REGISTERED = 8
    DISCONNECTING = 9

class ModemStateChangeReason(OrderedEnum):
    UNKNOWN = 0
    USER_REQUESTED = 1
    SUSPEND = 2
    FAILURE = 3
    
class ModemStateFailedReason(OrderedEnum):
    NONE = 0
    UNKNOWN = 1
    SIM_MISSING = 2
    SIM_ERROR = 3

class OmaSessionState(OrderedEnum):
    FAILED = -1
    UNKNOWN = 0
    STARTED = 1
    MDN_DOWNLOADED = 10
    MSID_DOWNLOADED = 11
    PRL_DOWNLOADED = 12
    MIP_PROFILE_DOWNLOADED = 13
    RETRYING = 2
    COMPLETED = 20
    CONNECTING = 3
    CONNECTED = 4
    AUTHENTICATED = 5

class OmaSessionStateFailedReason(OrderedEnum):
    UNKNOWN = 0
    NETWORK_UNAVAILABLE = 1
    SERVER_UNAVAILABLE = 2
    AUTHENTICATION_FAILED = 3
    MAX_RETRY_EXCEEDED = 4
    SESSION_CANCELLED = 5

class OmaSessionType(OrderedEnum):
    UNKNOWN = 0
    CLIENT_INITIATED_DEVICE_CONFIGURE = 10
    CLIENT_INITIATED_PRL_UPDATE = 11
    CLIENT_INITIATED_HANDS_FREE_ACTIVATION = 12
    NETWORK_INITIATED_DEVICE_CONFIGURE = 20
    NETWORK_INITIATED_PRL_UPDATE = 21
    DEVICE_INITIATED_PRL_UPDATE = 30
    DEVICE_INITIATED_HANDS_FREE_ACTIVATION = 31

class SerialError(OrderedEnum):
    UNKNOWN = 0
    OPENFAILED = 1
    SENDFAILED = 2
    RESPONSETIMEOUT = 3
    OPENFAILEDNODEVICE = 4
    FLASHFAILED = 5
    NOTOPEN = 6
    PARSEFAILED = 7
    FRAMENOTFOUND = 8

class SmsCdmaServiceCategory(OrderedEnum):
    UNKNOWN = 0
    EMERGENCY_BROADCAST = 1
    BUSINESS_NEWS_NATIONAL = 10
    BUSINESS_NEWS_INTERNATIONAL = 11
    SPORTS_NEWS_LOCAL = 12
    SPORTS_NEWS_REGIONAL = 13
    SPORTS_NEWS_NATIONAL = 14
    SPORTS_NEWS_INTERNATIONAL = 15
    ENTERTAINMENT_NEWS_LOCAL = 16
    ENTERTAINMENT_NEWS_REGIONAL = 17
    ENTERTAINMENT_NEWS_NATIONAL = 18
    ENTERTAINMENT_NEWS_INTERNATIONAL = 19
    ADMINISTRATIVE = 2
    LOCAL_WEATHER = 20
    TRAFFIC_REPORT = 21
    FLIGHT_SCHEDULES = 22
    RESTAURANTS = 23
    LODGINGS = 24
    RETAIL_DIRECTORY = 25
    ADVERTISEMENTS = 26
    STOCK_QUOTES = 27
    EMPLOYMENT = 28
    HOSPITALS = 29
    MAINTENANCE = 3
    TECHNOLOGY_NEWS = 30
    MULTICATEGORY = 31
    GENERAL_NEWS_LOCAL = 4
    CMAS_PRESIDENTIAL_ALERT = 4096
    CMAS_EXTREME_THREAT = 4097
    CMAS_SEVERE_THREAT = 4098
    CMAS_CHILD_ABDUCTION_EMERGENCY = 4099
    CMAS_TEST = 4100
    GENERAL_NEWS_REGIONAL = 5
    GENERAL_NEWS_NATIONAL = 6
    GENERAL_NEWS_INTERNATIONAL = 7
    BUSINESS_NEWS_LOCAL = 8
    BUSINESS_NEWS_REGIONAL = 9

class SmsCdmaTeleserviceId(OrderedEnum):
    UNKNOWN = 0
    CMT91 = 4096
    WPT = 4097
    WMT = 4098
    VMN = 4099
    WAP = 4100
    WEMT = 4101
    SCPT = 4102
    CATPT = 4103

class SmsDeliveryState(OrderedEnum):
    COMPLETED_RECEIVED = 0
    COMPLETED_FORWARDED_UNCONFIRMED = 1
    TEMPORARY_FATAL_ERROR_QOS_NOT_AVAILABLE = 100
    TEMPORARY_FATAL_ERROR_IN_SME = 101
    COMPLETED_REPLACED_BY_SC = 2
    UNKNOWN = 256
    TEMPORARY_ERROR_CONGESTION = 32
    TEMPORARY_ERROR_SME_BUSY = 33
    TEMPORARY_ERROR_NO_RESPONSE_FROM_SME = 34
    TEMPORARY_ERROR_SERVICE_REJECTED = 35
    TEMPORARY_ERROR_QOS_NOT_AVAILABLE = 36
    TEMPORARY_ERROR_IN_SME = 37
    NETWORK_PROBLEM_ADDRESS_VACANT = 512
    NETWORK_PROBLEM_ADDRESS_TRANSLATION_FAILURE = 513
    NETWORK_PROBLEM_NETWORK_RESOURCE_OUTAGE = 514
    NETWORK_PROBLEM_NETWORK_FAILURE = 515
    NETWORK_PROBLEM_INVALID_TELESERVICE_ID = 516
    NETWORK_PROBLEM_OTHER = 517
    TERMINAL_PROBLEM_NO_PAGE_RESPONSE = 544
    TERMINAL_PROBLEM_DESTINATION_BUSY = 545
    TERMINAL_PROBLEM_NO_ACKNOWLEDGMENT = 546
    TERMINAL_PROBLEM_DESTINATION_RESOURCE_SHORTAGE = 547
    TERMINAL_PROBLEM_SMS_DELIVERY_POSTPONED = 548
    TERMINAL_PROBLEM_DESTINATION_OUT_OF_SERVICE = 549
    TERMINAL_PROBLEM_DESTINATION_NO_LONGER_AT_THIS_ADDRESS = 550
    TERMINAL_PROBLEM_OTHER = 551
    RADIO_INTERFACE_PROBLEM_RESOURCE_SHORTAGE = 576
    RADIO_INTERFACE_PROBLEM_INCOMPATIBILITY = 577
    RADIO_INTERFACE_PROBLEM_OTHER = 578
    GENERAL_PROBLEM_ENCODING = 608
    GENERAL_PROBLEM_SMS_ORIGINATION_DENIED = 609
    GENERAL_PROBLEM_SMS_TERMINATION_DENIED = 610
    GENERAL_PROBLEM_SUPPLEMENTARY_SERVICE_NOT_SUPPORTED = 611
    GENERAL_PROBLEM_SMS_NOT_SUPPORTED = 612
    GENERAL_PROBLEM_MISSING_EXPECTED_PARAMETER = 614
    GENERAL_PROBLEM_MISSING_MANDATORY_PARAMETER = 615
    GENERAL_PROBLEM_UNRECOGNIZED_PARAMETER_VALUE = 616
    GENERAL_PROBLEM_UNEXPECTED_PARAMETER_VALUE = 617
    GENERAL_PROBLEM_USER_DATA_SIZE_ERROR = 618
    GENERAL_PROBLEM_OTHER = 619
    ERROR_REMOTE_PROCEDURE = 64
    ERROR_INCOMPATIBLE_DESTINATION = 65
    ERROR_CONNECTION_REJECTED = 66
    ERROR_NOT_OBTAINABLE = 67
    ERROR_QOS_NOT_AVAILABLE = 68
    ERROR_NO_INTERWORKING_AVAILABLE = 69
    ERROR_VALIDITY_PERIOD_EXPIRED = 70
    ERROR_DELETED_BY_ORIGINATING_SME = 71
    ERROR_DELETED_BY_SC_ADMINISTRATION = 72
    ERROR_MESSAGE_DOES_NOT_EXIST = 73
    TEMPORARY_NETWORK_PROBLEM_ADDRESS_VACANT = 768
    TEMPORARY_NETWORK_PROBLEM_ADDRESS_TRANSLATION_FAILURE = 769
    TEMPORARY_NETWORK_PROBLEM_NETWORK_RESOURCE_OUTAGE = 770
    TEMPORARY_NETWORK_PROBLEM_NETWORK_FAILURE = 771
    TEMPORARY_NETWORK_PROBLEM_INVALID_TELESERVICE_ID = 772
    TEMPORARY_NETWORK_PROBLEM_OTHER = 773
    TEMPORARY_TERMINAL_PROBLEM_NO_PAGE_RESPONSE = 800
    TEMPORARY_TERMINAL_PROBLEM_DESTINATION_BUSY = 801
    TEMPORARY_TERMINAL_PROBLEM_NO_ACKNOWLEDGMENT = 802
    TEMPORARY_TERMINAL_PROBLEM_DESTINATION_RESOURCE_SHORTAGE = 803
    TEMPORARY_TERMINAL_PROBLEM_SMS_DELIVERY_POSTPONED = 804
    TEMPORARY_TERMINAL_PROBLEM_DESTINATION_OUT_OF_SERVICE = 805
    TEMPORARY_TERMINAL_PROBLEM_DESTINATION_NO_LONGER_AT_THIS_ADDRESS = 806
    TEMPORARY_TERMINAL_PROBLEM_OTHER = 807
    TEMPORARY_RADIO_INTERFACE_PROBLEM_RESOURCE_SHORTAGE = 832
    TEMPORARY_RADIO_INTERFACE_PROBLEM_INCOMPATIBILITY = 833
    TEMPORARY_RADIO_INTERFACE_PROBLEM_OTHER = 834
    TEMPORARY_GENERAL_PROBLEM_ENCODING = 864
    TEMPORARY_GENERAL_PROBLEM_SMS_ORIGINATION_DENIED = 865
    TEMPORARY_GENERAL_PROBLEM_SMS_TERMINATION_DENIED = 866
    TEMPORARY_GENERAL_PROBLEM_SUPPLEMENTARY_SERVICE_NOT_SUPPORTED = 867
    TEMPORARY_GENERAL_PROBLEM_SMS_NOT_SUPPORTED = 868
    TEMPORARY_GENERAL_PROBLEM_MISSING_EXPECTED_PARAMETER = 870
    TEMPORARY_GENERAL_PROBLEM_MISSING_MANDATORY_PARAMETER = 871
    TEMPORARY_GENERAL_PROBLEM_UNRECOGNIZED_PARAMETER_VALUE = 872
    TEMPORARY_GENERAL_PROBLEM_UNEXPECTED_PARAMETER_VALUE = 873
    TEMPORARY_GENERAL_PROBLEM_USER_DATA_SIZE_ERROR = 874
    TEMPORARY_GENERAL_PROBLEM_OTHER = 875
    TEMPORARY_FATAL_ERROR_CONGESTION = 96
    TEMPORARY_FATAL_ERROR_SME_BUSY = 97
    TEMPORARY_FATAL_ERROR_NO_RESPONSE_FROM_SME = 98
    TEMPORARY_FATAL_ERROR_SERVICE_REJECTED = 99

class SmsPduType(OrderedEnum):
    UNKNOWN = 0
    DELIVER = 1
    SUBMIT = 2
    STATUS_REPORT = 3
    CDMA_DELIVER = 32
    CDMA_SUBMIT = 33
    CDMA_CANCELLATION = 34
    CDMA_DELIVERY_ACKNOWLEDGEMENT = 35
    CDMA_USER_ACKNOWLEDGEMENT = 36
    CDMA_READ_ACKNOWLEDGEMENT = 37

class SmsState(OrderedEnum):
    UNKNOWN = 0
    STORED = 1
    RECEIVING = 2
    RECEIVED = 3
    SENDING = 4
    SENT = 5

class SmsStorage(OrderedEnum):
    UNKNOWN = 0
    SM = 1
    ME = 2
    MT = 3
    SR = 4
    BM = 5
    TA = 6

class SmsValidityType(OrderedEnum):
    UNKNOWN = 0
    RELATIVE = 1
    ABSOLUTE = 2
    ENHANCED = 3