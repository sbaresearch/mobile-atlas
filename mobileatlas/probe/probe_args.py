import argparse
from .measurement.test.test_args import TestParser



class ProbeParser(TestParser):
    # Since quectel are our default modems
    DEFAULT_MODEM_TYPE = "quectel"
    # Since our only SIM Server is currently running on 10.0.0.3:8888
    DEFAULT_SIM_SERVER_IP = "10.0.0.3"
    DEFAULT_SIM_SERVER_PORT = 8888
    DEFAULT_TEST_TIMEOUT = 3600  # in seconds -> 60min

    CONFIG_SCHEMA_PROBE = {
        "type" : "object",
        "properties" : {
            "module_blacklist" : { "type" : "array", "default": []}
        }
    }
    
    def add_arguments(self):
        super().add_arguments()
        self.parser.add_argument('--modem', choices=['quectel', 'huawei', 'telit', 'simcom'],
                        default=ProbeParser.DEFAULT_MODEM_TYPE, help='Modem model that is used within the test environment (default: %(default)s)')
        self.parser.add_argument('--host', default=ProbeParser.DEFAULT_SIM_SERVER_IP,
                            help='SIM server address (default: %(default)s)')
        self.parser.add_argument('--port', type=int, default=ProbeParser.DEFAULT_SIM_SERVER_PORT,
                            help='SIM server port (default: %(default)d)')
        self.parser.add_argument('--timeout', type=int, default=ProbeParser.DEFAULT_TEST_TIMEOUT,
                            help='Test timeout (default: %(default)d)')
        self.parser.add_argument('--no-namespace', dest='start_namespace', action='store_false',
                            help='Do not start a separate measurement namespace (start test in native envorionment)')
        self.add_config_schema(ProbeParser.CONFIG_SCHEMA_PROBE)
        
    def parse(self):
        super().parse()
        if not self.is_measurement_namespace_enabled and self.is_debug_bridge_enabled():
            raise ValueError("If measurement namespace is disabled (--no-namespace), it is not possible to start a port forwarding (--debug-bridge).")

    def get_modem_type(self):
        return self.test_args.modem

    def get_host(self):
        return self.test_args.host

    def get_port(self):
        return self.test_args.port

    def get_timeout(self):
        return self.test_args.timeout

    def is_measurement_namespace_enabled(self):
        return self.test_args.start_namespace

    def get_blacklisted_modules(self):
        return self.test_config.get('module_blacklist', [])

    def setup_logging(self, log_file_name = "probe.log"):
        return super().setup_logging(log_file_name)