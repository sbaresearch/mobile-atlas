# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import logging
from queue import Queue
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.payload.payload_base import PayloadBase, PayloadResult

logger = logging.getLogger(__name__)

class PayloadUssd(PayloadBase):
    LOGGER_TAG = "payload_ussd"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, ussd_code = "*101#", wait_for_response=True, use_sms = False, use_call = False, use_ussd = True, use_connection = False, use_internet_gw = False):
        super().__init__(mobile_atlas_mediator, use_sms = use_sms, use_call = use_call, use_ussd = use_ussd, use_connection = use_connection, use_internet_gw = use_internet_gw)
        self.ussd_queue = Queue()
        self.ussd_code = ussd_code
        self.wait_for_response = wait_for_response

    def ussd_notification_received(self, message):
        self.ussd_queue.put(message)

    def send_payload(self) -> PayloadResult:
        self.ussd_queue = Queue() # clear queue
        #response = self.mobile_atlas_mediator.send_ussd_code(code="*121#")
        self.mobile_atlas_mediator.send_ussd_code_at(code=self.ussd_code)
        if self.wait_for_response:
            response = self.ussd_queue.get(timeout=30)
            logger.info(f"ussd response was {response}")
            return PayloadResult(True, response)
        return PayloadResult(False, None)