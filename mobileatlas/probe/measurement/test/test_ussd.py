
from mobileatlas.probe.measurement.payload.payload_ussd import PayloadUssd
from mobileatlas.probe.measurement.test.test_base import TestBase


class TestUssd(TestBase):
    DEFAULT_USSD_CODE = "*101#"

    CONFIG_SCHEMA_RECONNECT = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "ussd_code" : { "type" : "string", "default" : DEFAULT_USSD_CODE}
                }
            }
        }
    }

    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestUssd.CONFIG_SCHEMA_RECONNECT)

    def get_ussd_code(self):
        return self.parser.test_config.get("test_params.ussd_code", TestUssd.DEFAULT_USSD_CODE)

    def execute_test_core(self):
        payload = PayloadUssd(self.mobile_atlas_mediator)
        payload.execute()