#!/usr/bin/env python3

import logging
from mobileatlas.probe.measurement.utils.ec2 import Ec2Instance
from mobileatlas.probe.measurement.credit.credit_checker import CreditChecker
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.payload.payload_network_web import PayloadNetworkWeb, PayloadNetworkWebControlTraffic
from .test_network_base import TestNetworkBase

logger = logging.getLogger(__name__)

class TestNetworkZeroBase(TestNetworkBase):
    DEFAULT_PROTOCOLS = ["https", "http", "quic"]

    def __init__(self, parser: TestParser):
        super().__init__(parser, use_credit_checker=True)

    def get_url_zero_rated(self):
        raise NotImplementedError("method not implemented")

    def get_protocols(self):
        raise NotImplementedError("method not implemented")

    def get_fixed_ip(self):
        return None

    def get_sni_host(self):
        return None

    def execute_test_network_core(self):
        print(f"execute_test_network_core start")
        size = CreditChecker.DEFAULT_BYTES  # usually 1megabyte
        if self.credit_checker:
            size = self.credit_checker.get_minimum_billing_unit()
        
        logger.info(f"starting with {size} bytes")

        for protocol in self.get_protocols():
            logger.info(f"starting {protocol} payload (size: {size})")
            payload_zero = PayloadNetworkWeb(self.mobile_atlas_mediator, payload_size=size, url=self.get_url_zero_rated(), force_protocol=protocol, fix_target_ip=self.get_fixed_ip(), override_sni_host=self.get_sni_host())
            ret = payload_zero.execute()
            logger.info(f"{protocol} payload finished (success: {ret.success}), rx {ret.consumed_bytes_rx}, tx {ret.consumed_bytes_tx} bytes")
            size *= 2

        logger.info(f"starting control payload (size: {size})")
        payload_control = PayloadNetworkWebControlTraffic(self.mobile_atlas_mediator, payload_size=size, protocol='https')
        ret = payload_control.execute()
        self.credit_checker.add_consumed_units({"traffic_bytes_total" : size})  #add control bytes to billed bytes
        logger.info(f"control traffic payload finished (success: {ret.success}), rx {ret.consumed_bytes_rx}, tx {ret.consumed_bytes_tx} bytes")

        print(f"execute_test_network_core finished")



class TestNetworkZero(TestNetworkZeroBase):
    DEFAULT_URL_ZERO = "https://app.snapchat.com/web/deeplink/snapcode?username=michelleobama&type=SVG&size=240" #"https://app.snapchat.com/dmd/memories"

    #https://scontent-vie1-1.xx.fbcdn.net/v/t1.6435-9/106567740_10112084545410921_8506334020973196184_n.jpg?_nc_cat=105&ccb=1-3&_nc_sid=174925&_nc_ohc=ZFvGlQhPMU8AX_C7mUx&_nc_ht=scontent-vie1-1.xx&oh=e70796c830185b0138645ebd63a77536&oe=60EC87CC
    
    #"https://graph.facebook.com/v11.0/me/messages" #"https://web.whatsapp.com/img/favicon/1x/favicon.png"
    #"https://app.snapchat.com/dmd/memories"        #supports https, http and quic
    #"https://chatapi.viber.com/pa/send_message"    #only https (no http or quic)

    CONFIG_SCHEMA_NETWORK_ZERO_VALIDATE = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "url_zero_rated" : { "type" : "string", "default" : DEFAULT_URL_ZERO},
                    "protocols" : {"type": "array", "items": {"type": "string", "enum": TestNetworkZeroBase.DEFAULT_PROTOCOLS}, "default": TestNetworkZeroBase.DEFAULT_PROTOCOLS}
                }
            }
        }
    }

    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestNetworkZero.CONFIG_SCHEMA_NETWORK_ZERO_VALIDATE)

    def get_url_zero_rated(self):
        return self.parser.test_config.get("test_params.url_zero_rated", TestNetworkZero.DEFAULT_URL_ZERO)

    def get_protocols(self):
        return self.parser.test_config.get("test_params.protocols", TestNetworkZeroBase.DEFAULT_PROTOCOLS)


class TestNetworkZeroCheckSni(TestNetworkZero):
    def __init__(self, parser: TestParser):
        super().__init__(parser)
        self.ec2 = None
        self.ec2_ip = None

    def execute_test_network_pre(self):
        #first do ec2 shit
        self.mobile_atlas_mediator.enable_veth_gateway()
        # TODO: load ec2 id and key from environment variable or config
        self.ec2 = Ec2Instance(id='xxx', key='xxx')
        self.ec2.start_instance_web_forward(self.get_url_zero_rated())
        self.ec2_ip = self.ec2.get_ip()
        self.mobile_atlas_mediator.disable_veth_gateway()

        # then call super method
        super().execute_test_network_pre()

    def execute_test_network_post(self):
        # first call super method
        super().execute_test_network_post()
        # then do ec2 shutdown
        self.mobile_atlas_mediator.enable_veth_gateway()
        self.ec2.stop_instance()
        self.mobile_atlas_mediator.disable_veth_gateway()

    def get_fixed_ip(self):
        return self.ec2_ip

class TestNetworkZeroCheckIp(TestNetworkZero):
    DEFAULT_SNI_HOST = "example.com"

    CONFIG_SCHEMA_NETWORK_ZERO_CHECK_IP = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "sni_host" : { "type" : "string", "default" : DEFAULT_SNI_HOST},
                }
            }
        }
    }

    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestNetworkZeroCheckIp.CONFIG_SCHEMA_NETWORK_ZERO_CHECK_IP)

    def get_sni_host(self):        
        return self.parser.test_config.get("test_params.sni_host", TestNetworkZeroCheckIp.DEFAULT_SNI_HOST)