# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

from mobileatlas.probe.measurement.test.test_base import TestBase
from mobileatlas.probe.measurement.payload.payload_sms import PayloadSms


class TestSms(TestBase):

    CONFIG_SCHEMA_RECONNECT = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "sms_number" : { "type" : "string"},
                    "sms_text" : { "type" : "string"},
                    "sms_wait_for_response" : { "type" : "boolean", "default" : False}
                },
                "required": ["sms_number", "sms_text"]
            }
        },
        "required": ["test_params"]
    }

    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestSms.CONFIG_SCHEMA_RECONNECT)

    def get_sms_number(self):
        return self.parser.test_config.get("test_params.sms_number", None)
    
    def get_sms_text(self):
        return self.parser.test_config.get("test_params.sms_text", None)

    def sms_wait_for_response(self):
        return self.parser.test_config.get("test_params.sms_wait_for_response", False)

    def execute_test_core(self):
        payload = PayloadSms(self.mobile_atlas_mediator, number=self.get_sms_number(), text=self.get_sms_text(), wait_for_response=self.sms_wait_for_response())
        payload.execute()