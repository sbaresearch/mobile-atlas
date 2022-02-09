#!/usr/bin/env python3

import logging
from mobileatlas.probe.measurement.credit.credit_checker import CreditChecker
from mobileatlas.probe.measurement.payload.payload_public_ip import PayloadPublicIp
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.payload.payload_network_web import PayloadNetworkWeb, PayloadNetworkWebControlTraffic
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
from .test_network_base import TestNetworkBase

logger = logging.getLogger(__name__)

class PayloadEntry:
    def __init__(self, name, payload, add_to_consumed_units):
        self.name = name
        self.payload = payload #PayloadNetworkWeb
        self.add_to_consumed_units = add_to_consumed_units

class TestNetworkBillingBase(TestNetworkBase):
    def __init__(self, parser: TestParser):
        super().__init__(parser, use_credit_checker=True)
        self.payload_list = []
        self.next_paload_size = CreditChecker.DEFAULT_BYTES  # usually 1megabyte
        if self.credit_checker:
            self.next_paload_size = self.credit_checker.get_minimum_billing_unit()
        
    def add_network_payload(self, name, payload, add_to_consumed_units, double_next_payload_size=True):
        payload = PayloadEntry(name, payload, add_to_consumed_units)
        self.payload_list.append(payload)
        if double_next_payload_size:
            self.next_paload_size *= 2
        
    def get_next_payload_size(self):
        return self.next_paload_size
    
    def execute_test_network_core(self):
        print(f"start execute_test_network_core start")
        for payload_entry in self.payload_list:
            payload = payload_entry.payload
            logger.info(f"starting payload {payload.name} (size: {payload.payload_size})")
            ret = payload.execute()
            logger.info(f"payload {payload.name} finished (success: {ret.success}), rx {ret.consumed_bytes_rx}, tx {ret.consumed_bytes_tx} bytes")
            if payload_entry.add_to_consumed_units:
                bytes_consumed = payload.get_consumed_bytes()
                bytes_web_total = self.add_consumed_bytes(*bytes_consumed) #a1 did not recognize this, prolly better to use size instead of consumed bytes? alternatively make it somehow tolerant and multiply with factor 0,9? :X
        print(f"execute_test_network_core finished")
        

class TestNetworkBilling(TestNetworkBillingBase):
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
        super().__init__(parser)
        self.next_paload_size = self.get_size()   
        if self.get_include_ip_check():
            payload_ip = PayloadPublicIp(self.mobile_atlas_mediator)
            self.add_network_payload("payload_get_ip", payload_ip, False, False)
        if self.get_url_control_traffic():
            payload_web = PayloadNetworkWeb(self.mobile_atlas_mediator, payload_size=self.get_next_payload_size(), url=self.get_url_control_traffic())
            self.add_network_payload("payload_web_control", payload_web, True)
        else:
            payload_web = PayloadNetworkWebControlTraffic(self.mobile_atlas_mediator, payload_size=self.get_next_payload_size(), protocol='https')
            self.add_network_payload("payload_web_control", payload_web, True)

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