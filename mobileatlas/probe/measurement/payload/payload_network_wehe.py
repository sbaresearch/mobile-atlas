# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import logging
import subprocess

from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.payload.payload_base import PayloadBase
from .payload_network_base import PayloadNetworkBase, PayloadNetworkResult

logger = logging.getLogger(__name__)


class PayloadNetworkWehe(PayloadNetworkBase):
    LOGGER_TAG = "payload_network_wehe"
    WEHE_WD = PayloadBase.PAYLOAD_DIR + "res/wehe/"
    WEHE_CLIENT_JAR = "wehe-client.jar"
    # WEHE_TEST_DIR = PayloadBase.PAYLOAD_DIR + "res/wehe/tests/"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, wehe_server, test_name, results_dir):
        super().__init__(mobile_atlas_mediator)
        self.wehe_server = wehe_server
        self.test_name = test_name # WEHE_TEST_DIR + test_name
        self.results_dir = results_dir

    def send_payload(self) -> PayloadNetworkResult:
        logger.info("starting wehe client")

        # TODO: maybe use pexpect instead subprocess to be consistent with other subprocess calls
        subprocess.run(["java", "-jar", PayloadNetworkWehe.WEHE_CLIENT_JAR,
            "-s", self.wehe_server,
            "-n", self.test_name,
            "-r", self.results_dir], cwd=PayloadNetworkWehe.WEHE_WD)

        return PayloadNetworkResult(True, None, *self.get_consumed_bytes(), 0)

