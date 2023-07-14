#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import time
import argparse
import sys

from .test_base import TestBase
from .test_config import TestConfig

class TestInteractive(TestBase):
    def execute_test_core(self):
        print("wait until modem is plugged in...")
        self.wait_modem_added()
        print("wait until modem is ready...")
        self.wait_modem_registered()

        while True:
            cmd = input()
            #print("input " + cmd)
            if cmd == "exit":
                break
            elif cmd.startswith("call "):
                number = cmd[len("call "):]
                self.mm.call_ping(number=number, ringtime=12)
            elif cmd.startswith("ussd "):
                code = cmd[len("ussd "):]
                self.mm.send_ussd(code=code)
            elif cmd.startswith("network "):
                network_id = cmd[len("network "):]
                self.mm.register_network(network_id=network_id)
            elif cmd == "scan":
                self.mm.scan_networks()
            elif cmd.startswith("connect "):
                provider = cmd[len("connect "):]
                settings = TestConfig.get_apn_config(provider)
                if settings is not None:
                    apn = settings.get("apn")
                    username = settings.get("username")
                    password = settings.get("password")

                    self.wait_modem_registered()
                    print("trying to connect")
                    self.connect_modem(apn, username, password)
            elif cmd == 'disconnect':
                self.disconnect_modem()
            elif cmd == "scan":
                self.disconnect_modem()
                print("wait...")
                self.wait_modem_registered()