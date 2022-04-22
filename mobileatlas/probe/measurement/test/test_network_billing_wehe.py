

from mobileatlas.probe.measurement.payload.payload_network_web import PayloadNetworkWebControlTraffic
from mobileatlas.probe.measurement.payload.payload_network_wehe import PayloadNetworkWehe
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.test.test_network_billing import TestNetworkBillingBase


class TestNetworkBillingWehe(TestNetworkBillingBase):
    DEFAULT_WEHE_RESULTS_DIR = "/tmp/mobileatlas/wehe/"
    
    CONFIG_SCHEMA_NETWORK_BILLING_WEHE = {
        "type": "object",
        "properties" : {
            "test_params" : {
                "type": "object",
                "properties" : {
                    "wehe_server" : { "type" : "string" },
                    "wehe_test_name" : { "type" : "string" },
                    "wehe_results_dir": { "type" : "string", "default" : DEFAULT_WEHE_RESULTS_DIR},
                }
            }
        }
    }

    def __init__(self, parser: TestParser):
        super().__init__(parser)
        self.next_paload_size = self.get_size()
        
        self.payload_wehe = PayloadNetworkWehe(self.mobile_atlas_mediator, wehe_server=self.get_wehe_server(), test_name=self.get_wehe_test_name(), results_dir=self.get_wehe_results_dir())
        self.add_network_payload("payload_wehe", self.payload_wehe, False)
        
        payload_web = PayloadNetworkWebControlTraffic(self.mobile_atlas_mediator, payload_size=0, protocol='https') # payload_size = 0 defaults to twice the size of previous payload
        self.add_network_payload("payload_web_control", payload_web, True)
        
    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestNetworkBillingWehe.CONFIG_SCHEMA_NETWORK_BILLING_WEHE)

    def get_wehe_server(self):
        return self.parser.test_config.get("test_params.wehe_server")
    
    def get_wehe_test_name(self):
        return self.parser.test_config.get("test_params.wehe_test_name")
    
    def get_wehe_results_dir(self):
        return self.parser.test_config.get("test_params.wehe_results_dir", TestNetworkBillingWehe.DEFAULT_WEHE_RESULTS_DIR)



