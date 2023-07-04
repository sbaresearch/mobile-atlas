#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

from mobileatlas.probe.measurement.utils.format_logging import format_extra
from mobileatlas.probe.measurement.test.test_args import TestParser
from .test_network_base import TestNetworkBase
from ..payload.payload_public_ip import PayloadPublicIp


class TestNetworkInfo(TestNetworkBase):
    def __init__(self, parser: TestParser):
        super().__init__(parser, use_credit_checker=True)

    def execute_test_network_core(self):
        payload = PayloadPublicIp(self.mobile_atlas_mediator)
        result = payload.execute()
        self.result_logger.info("TestNetworkInfo finished", extra=format_extra("test_results", result))
        used_bytes = payload.get_consumed_bytes()
        bytes_web_total = self.add_consumed_bytes(*used_bytes)
