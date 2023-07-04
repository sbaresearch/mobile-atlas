# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import logging
from mobileatlas.probe.measurement.mediator.mm_definitions import ModemManagerSms, SmsState
from queue import Queue
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.payload.payload_base import PayloadBase, PayloadResult

logger = logging.getLogger(__name__)

class PayloadSms(PayloadBase):
    LOGGER_TAG = "payload_sms"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, number, text, wait_for_response=True, use_sms = True, use_call = False, use_ussd = False, use_connection = False, use_internet_gw = False):
        super().__init__(mobile_atlas_mediator, use_sms = use_sms, use_call = use_call, use_ussd = use_ussd, use_connection = use_connection, use_internet_gw = use_internet_gw)
        self.sms_queue = Queue()
        self.number = number
        self.text = text
        self.wait_for_response = wait_for_response

    def sms_received(self, sms: ModemManagerSms):
        if sms.get_state() == SmsState.RECEIVED:
            self.sms_queue.put(sms)

    def send_payload(self) -> PayloadResult:
        self.sms_queue = Queue() # clear queue
        self.mobile_atlas_mediator.send_sms(number=self.number, text=self.text)
        if self.wait_for_response:
            response = self.sms_queue.get(timeout=30)
            logger.info(f"sms response was {response.to_dict()}")
            return PayloadResult(True, response)
        return PayloadResult(False, None)
