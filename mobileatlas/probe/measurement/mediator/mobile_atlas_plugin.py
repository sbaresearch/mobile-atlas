
from mobileatlas.probe.measurement.mediator.mm_definitions import ModemManagerSms, ModemManagerCall
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator


class MobileAtlasPlugin():
    LOGGER_TAG = "mobile_atlas_plugin"

    DEFAULT_TIMEOUT_REGISTERED = 1800
    DEFAULT_INTERVAL_REGISTERED_DEBOUNCED = 3

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator = None, use_sms = False, use_call = False, use_ussd = False, use_connection = False, use_internet_gw = False):
        self.mobile_atlas_mediator = mobile_atlas_mediator
        self.use_sms = use_sms
        self.use_call = use_call
        self.use_ussd = use_ussd
        self.use_connection = use_connection
        self.use_internet_gw = use_internet_gw

    def sms_received(self, sms: ModemManagerSms):
        pass
    
    def call_received(self, call: ModemManagerCall):
        pass

    def ussd_notification_received(self, message):
        pass

    def connection_state_changed(self, is_connected):
        pass

    def use_modem(self):
        return self.use_sms or self.use_call or self.use_ussd or self.use_connection

    # subscribe to stuff from mediator
    def setup_callbacks(self):
        if self.use_sms:
            self.mobile_atlas_mediator.add_sms_observer(self.sms_received)
        if self.use_call:
            self.mobile_atlas_mediator.add_call_observer(self.call_received)
        if self.use_ussd:
            self.mobile_atlas_mediator.add_ussd_observer(self.ussd_notification_received)
        if self.use_connection:
            self.mobile_atlas_mediator.add_connection_observer(self.connection_state_changed)
        # technically no callback, however this is the perfect moment to setup the ethernet bridge as well :)
        if self.use_internet_gw:
            self.mobile_atlas_mediator.enable_veth_gateway()

        if self.use_modem():
            self.mobile_atlas_mediator.wait_modem_registered(MobileAtlasPlugin.DEFAULT_TIMEOUT_REGISTERED, MobileAtlasPlugin.DEFAULT_INTERVAL_REGISTERED_DEBOUNCED)

    # remove subscriptions
    def remove_callbacks(self):
        # technically no callback, however see above
        if self.use_internet_gw:
            self.mobile_atlas_mediator.disable_veth_gateway()
        if self.use_connection:
            self.mobile_atlas_mediator.remove_connection_observer(self.connection_state_changed)
        if self.use_ussd:
            self.mobile_atlas_mediator.remove_ussd_observer(self.ussd_notification_received)
        if self.use_call:
            self.mobile_atlas_mediator.remove_call_observer(self.call_received)
        if self.use_sms:
            self.mobile_atlas_mediator.remove_sms_observer(self.sms_received)