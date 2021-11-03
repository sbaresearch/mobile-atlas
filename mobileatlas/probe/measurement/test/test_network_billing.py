#!/usr/bin/env python3

from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from mobileatlas.probe.measurement.credit.credit_checker import CreditChecker
from mobileatlas.probe.measurement.test.test_network_base import TestNetworkBase
from mobileatlas.probe.measurement.payload.payload_public_ip import PayloadPublicIp
from mobileatlas.probe.measurement.payload.payload_network_web import PayloadNetworkWeb, PayloadNetworkWebControlTraffic
from mobileatlas.probe.measurement.utils.format_logging import format_extra
from mobileatlas.probe.measurement.test.test_args import TestParser



class TestNetworkBilling(TestNetworkBase):
    CONFIG_SCHEMA_NETWORK_BILLING = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "include_ip_check" : { "type": "boolean", "default": True},
                    "url_control_traffic" : { "type" : "string"},
                    "size" : { "type": "integer"}
                }
            }
        }
    }

    def __init__(self, parser: TestParser):
        super().__init__(parser, use_credit_checker=True)

    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestNetworkBilling.CONFIG_SCHEMA_NETWORK_BILLING)

    def get_include_ip_check(self):
        return self.parser.test_config.get("test_params.include_ip_check")

    def get_url_control_traffic(self):
        return self.parser.test_config.get("test_params.url_control_traffic")

    
    def get_size(self):
        size = self.parser.test_config.get("test_params.size", None)
        if size:
            size = convert_size_to_bytes(f'{size} MB')
        else:
            if self.credit_checker:
                size = self.credit_checker.get_minimum_billing_unit()
            else:
                size = CreditChecker.DEFAULT_BYTES # usually 1megabyte
        return size

    def execute_test_network_core(self):
        size = self.get_size()

        if self.get_include_ip_check():
            payload_ip = PayloadPublicIp(self.mobile_atlas_mediator)
            result_ip = payload_ip.execute()
            self.result_logger.info("PayloadPublicIp finished", extra=format_extra("payload_results", result_ip))
            bytes_ip = payload_ip.get_consumed_bytes()
            bytes_ip_total = self.add_consumed_bytes(*bytes_ip) 
            size -= bytes_ip_total

        if self.get_url_control_traffic():
            payload_web = PayloadNetworkWeb(self.mobile_atlas_mediator, payload_size=size, url=self.get_url_control_traffic())
        else:
            payload_web = PayloadNetworkWebControlTraffic(self.mobile_atlas_mediator, payload_size=size, protocol='https')
        
        result_web = payload_web.execute()
        self.result_logger.info("PayloadNetworkWeb finished", extra=format_extra("payload_results", result_web))
        bytes_web = payload_web.get_consumed_bytes()
        bytes_web_total = self.add_consumed_bytes(*bytes_web) #a1 did not recognize this, prolly better to use size instead of consumed bytes? alternatively make it tolerant and multiply with factor 0,9? :X