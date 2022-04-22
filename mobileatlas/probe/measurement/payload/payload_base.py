from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.mediator.mobile_atlas_plugin import MobileAtlasPlugin

class PayloadResult:
    def __init__(self, success, result):
        self.success = success
        self.result = result



class PayloadBase(MobileAtlasPlugin):
    LOGGER_TAG = "payload_base"
    PAYLOAD_DIR = "mobileatlas/probe/measurement/payload/"

    #def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, use_sms = False, use_call = False, use_connection = False, use_internet_gw = False):
    #    super().__init__(mobile_atlas_mediator, use_sms , use_call, use_connection, use_internet_gw)

    def send_payload(self) -> PayloadResult:
        pass

    def execute(self):
        self.setup_callbacks()
        #self.add_timestamp('payload_start_time')
        ret = self.send_payload()
        #self.add_timestamp('payload_start_time')
        self.remove_callbacks()
        return ret
