#!/usr/bin/env python3

from mobileatlas.probe.measurement.test.test_network_billing import TestNetworkBilling
from mobileatlas.probe.measurement.test.test_network_base import TestNetworkBase
from mobileatlas.probe.measurement.test.test_network_zero_web import TestNetworkZeroWeb, TestNetworkZeroWebCheckIp, TestNetworkZeroWebCheckSni
from mobileatlas.probe.measurement.test.test_sms import TestSms
from mobileatlas.probe.measurement.test.test_ussd import TestUssd
from .test_base import TestBase
from .test_network_info import TestNetworkInfo
from .test_network_reconnect import TestNetworkReconnect
from .test_interactive import TestInteractive

class TestFactory:
    def __init__(self):
        self._creators = {}

    def register_test(self, test_name, creator):
        self._creators[test_name] = creator

    def get_test(self, test_name, parser) -> TestBase:
        creator = self._creators.get(test_name)
        if not creator:
            raise ValueError(test_name)
        return creator(parser)

    def is_test_available(self, test_name):
        return self._creators.get(test_name) is not None


test_factory = TestFactory()
test_factory.register_test('TestBase', TestBase)
test_factory.register_test('TestNetworkBase', TestNetworkBase)
test_factory.register_test('TestNetworkInfo', TestNetworkInfo)
test_factory.register_test('TestNetworkReconnect', TestNetworkReconnect)
test_factory.register_test('TestNetworkBilling', TestNetworkBilling)
test_factory.register_test('TestNetworkZeroWeb', TestNetworkZeroWeb)
test_factory.register_test('TestNetworkZeroWebCheckIp', TestNetworkZeroWebCheckIp)
test_factory.register_test('TestNetworkZeroWebCheckSni', TestNetworkZeroWebCheckSni)
test_factory.register_test('TestUssd', TestUssd)
test_factory.register_test('TestSms', TestSms)
test_factory.register_test('TestInteractive', TestInteractive)
