

from mobileatlas.probe.measurement.payload.payload_network_dns import PayloadNetworkDns
from mobileatlas.probe.measurement.payload.payload_network_web import PayloadNetworkWebControlTrafficWithIpCheck
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.test.test_network_billing import TestNetworkBillingBase
from mobileatlas.probe.measurement.utils.ec2 import Ec2Instance


class TestNetworkBillingDns(TestNetworkBillingBase):
    CONFIG_SCHEMA_NETWORK_BILLING_DNS = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "dns_server" :  { "type" : "string"}
                }
            }
        }
    }
    def __init__(self, parser: TestParser):
        super().__init__(parser)
        self.next_paload_size = self.get_size()
        
        dns_server="primary"    #use primary dns per default
        if self.get_dns_server():
            dns_server=[self.get_dns_server()] #otherwise use dns server from config file
        
        self.payload_dns = PayloadNetworkDns(self.mobile_atlas_mediator, self.get_next_payload_size(), nameservers=dns_server)
        self.add_network_payload("payload_dns", self.payload_dns, False)
        
        payload_web = PayloadNetworkWebControlTrafficWithIpCheck(self.mobile_atlas_mediator, payload_size=self.get_next_payload_size(), protocol='https')
        self.add_network_payload("payload_web_control", payload_web, True)
        
    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestNetworkBillingDns.CONFIG_SCHEMA_NETWORK_BILLING_DNS)

    def get_dns_server(self):
        return self.parser.test_config.get("test_params.dns_server")

    def get_relay_dns(self):
        return self.parser.test_config.get("test_params.relay_dns")

class TestNetworkBillingDnsEc2Relay(TestNetworkBillingDns):
    def __init__(self, parser: TestParser):
        super().__init__(parser)
        self.ec2 = None
        self.ec2_ip = None

    def execute_test_network_pre(self):
        #first do ec2 shit
        self.mobile_atlas_mediator.enable_veth_gateway()
        # TODO: load ec2 id and key from environment variable or config
        self.ec2 = Ec2Instance()
        self.ec2.start_instance_forward_dns("8.8.8.8")
        self.ec2_ip = self.ec2.get_ip()
        self.mobile_atlas_mediator.disable_veth_gateway()
        
        #adjust nameserver of dns payload
        self.payload_dns.nameservers = [self.ec2_ip]

        # then call super method
        super().execute_test_network_pre()

    def execute_test_network_post(self):
        # first call super method
        super().execute_test_network_post()
        # then do ec2 shutdown
        self.mobile_atlas_mediator.enable_veth_gateway()
        self.ec2.stop_instance()
        self.mobile_atlas_mediator.disable_veth_gateway()
        
    #def get_size(self):
    #    return convert_size_to_bytes(f'{500} KB')