#!/usr/bin/env python3

from mobileatlas.probe.measurement.utils.format_logging import format_extra
from mobileatlas.probe.measurement.test.test_args import TestParser
import os
import json
import psutil
import logging

from .test_base import TestBase
from .test_config import TestConfig

logger = logging.getLogger(__name__)

class TestNetworkBase(TestBase):
    DEFAULT_URL_BILLED_TRAFFIC_100KB = "http://speedtest.tele2.net/100KB.zip"
    DEFAULT_URL_BILLED_TRAFFIC = DEFAULT_URL_BILLED_TRAFFIC_100KB

    CONFIG_SCHEMA_NETWORK_BASE = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "apn" : { "type" : "string"},
                    "username" : { "type" : "string"},
                    "password" : { "type" : "string"},
                    "network_id" : { "type" : "string"}
                }
            }
        }
    }

    def __init__(self, parser: TestParser, use_credit_checker=False):
        super().__init__(parser, use_credit_checker=use_credit_checker)
        self.use_connection = True

    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestNetworkBase.CONFIG_SCHEMA_NETWORK_BASE)
    
    def get_apn(self):
        return self.parser.test_config.get("test_params.apn", None)

    def get_username(self):
        return self.parser.test_config.get("test_params.username", None)

    def get_password(self):
        return self.parser.test_config.get("test_params.password", None)

    def get_network_id(self):
        return self.parser.test_config.get("test_params.network_id", None)

    def connection_state_changed(self, is_connected):
        if is_connected:
            self.add_consumed_units({"traffic_cnt_connections" : 1})

    def add_consumed_bytes(self, bytes_down, bytes_up):
        total = bytes_down + bytes_up
        u = {
            "traffic_bytes_downstream": bytes_down,
            "traffic_bytes_upstream": bytes_up,
            "traffic_bytes_total" : total
        }
        self.add_consumed_units(u)
        return total

    def get_network_interface_addresses(self):
        # TODO implement  psutil.net_if_addrs()
        pass

    def get_network_interface_stats(self):
        # TODO implement  psutil.net_if_stats()
        pass

    def add_network_interface_snapshot(self, tag):
        snapshot = self.mobile_atlas_mediator.get_network_interface_snapshot()
        self.result_logger.debug(f'network_interface_snapshot: {tag}', extra=format_extra(tag, {'snapshot': snapshot}))

    def dump_external_ip(self, endpoint="https://wtfismyip.com/json"):
        import requests
        ip_json = requests.get(endpoint).json
        logging.info(f"dump_external_ip: {ip_json}")

    def connect_network(self):
        #print("wait until modem is plugged in...")
        self.mobile_atlas_mediator.wait_modem_added()

        self.mobile_atlas_mediator.wait_modem_registered(timeout = 1200, preserve_state_timeout = 5)

        logger.info("modem is registered, ready to connect")
        self.mobile_atlas_mediator.connect_modem(self.get_apn(), self.get_username(), self.get_password(), self.get_network_id())
        logger.info("modem is connected")

    def disconnect_network(self):
        logger.info("disconnect modem again...")
        self.mobile_atlas_mediator.disconnect_modem()
        logger.info("modem successfully disconnected")

    def execute_test_network_pre(self):
        self.connect_network()
        self.add_network_interface_snapshot('networktest_start')

    def execute_test_network_post(self):
        self.add_network_interface_snapshot('networktest_stop')
        self.disconnect_network()

    def execute_test_network_core(self):
        while True:
            cmd = input()
            if cmd == "exit":
                break

    def execute_test_core(self):
        self.execute_test_network_pre()
        self.execute_test_network_core()
        self.execute_test_network_post()

