#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

from .test_network_base import TestNetworkBase

class TestNetworkReconnect(TestNetworkBase):
    DEFAULT_RECONNECT_CNT = 5

    CONFIG_SCHEMA_RECONNECT = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "reconnect_cnt" : { "type" : "integer", "default" : DEFAULT_RECONNECT_CNT}
                }
            }
        }
    }

    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestNetworkReconnect.CONFIG_SCHEMA_RECONNECT)

    def get_reconnect_cnt(self):
        return self.parser.test_config.get("test_params.reconnect_cnt", TestNetworkReconnect.DEFAULT_RECONNECT_CNT)

    def execute_test_network_core(self):
        for i in range(self.parser.get_reconnect_cnt()):
            self.disconnect_network()
            self.connect_network()