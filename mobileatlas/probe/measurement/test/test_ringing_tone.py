#!/usr/bin/env python3

from queue import Queue
import time
import datetime
import pexpect
import logging
from mobileatlas.probe.measurement.mediator.mm_definitions import CallState, ModemManagerCall

from mobileatlas.probe.measurement.test.test_args import TestParser
from .test_base import TestBase
from .test_config import TestConfig

logger = logging.getLogger(__name__)

class TestRingingTone(TestBase):
    DEFAULT_VOICE_RESULTS_DIR = "/tmp/mobileatlas/"
    
    CONFIG_SCHEMA_RINGING_TONE = {
        "type": "object",
        "properties" : {
            "test_params" : {
                "type": "object",
                "properties" : {
                    "target_number" : { "type" : "string" },
                    "voice_results_dir": { "type" : "string", "default" : DEFAULT_VOICE_RESULTS_DIR},
                }
            }
        }
    }
    
    def __init__(self, parser: TestParser):
        super().__init__(parser, use_call = True)
        self.dialing_queue = Queue()
        self.ringing_queue = Queue()
        self.active_queue = Queue()
        
    def validate_test_config(self):
        super().validate_test_config()
        self.parser.validate_test_config_schema(TestRingingTone.CONFIG_SCHEMA_RINGING_TONE)

    def get_target_number(self):
        return self.parser.test_config.get("test_params.target_number")

    def get_voice_results_dir(self):
        return self.parser.test_config.get("test_params.voice_results_dir", TestRingingTone.DEFAULT_VOICE_RESULTS_DIR)
    
    def start_recording(self, prefix='recording'):
        time_str = datetime.datetime.utcnow().isoformat()
        filename = f"{prefix}_{time_str}.wav"
        filename = self.get_voice_results_dir() + filename
        ps_rec = pexpect.spawn(f"arecord -D hw:1,0,0 -f S16_LE {filename}")
        return ps_rec

    def stop_recording(self, ps_rec):
        #ps_rec.sendcontrol('c')
        #ps_rec.kill(signal)
        ps_rec.terminate() #force=True
        ps_rec.wait()

    def call_received(self, call: ModemManagerCall):
        if call.get_number() == self.get_target_number():
            if call.get_state() == CallState.DIALING:
                self.dialing_queue.put(time.time())
            elif call.get_state() == CallState.RINGING_OUT:
                self.ringing_queue.put(time.time())
            elif call.get_state() == CallState.ACTIVE:
                self.active_queue.put(time.time())
    
    def execute_test_core(self):
        print("wait until modem is ready...")
        self.mobile_atlas_mediator.wait_modem_registered(timeout = 1200, preserve_state_timeout = 10)
                
        number = self.get_target_number()
        ps_rec = self.start_recording(prefix=f"ringing_tone_{number}")
        #self.mobile_atlas_mediator.call_ping(number=number, ringtime=30)
        call = self.mobile_atlas_mediator.create_call(number=number)

        self.mobile_atlas_mediator.send_at_command('AT+COPS?') # just to flush the buffer?
        
        self.mobile_atlas_mediator.start_call(call)
        time_dialing = self.dialing_queue.get(timeout=20)
        time_ringing = self.ringing_queue.get(timeout=30)
        dial_duration = time_ringing - time_dialing
        logger.info(f"dial duration: {dial_duration}", {"dial_duration" : dial_duration, "time_dialing" : time_dialing, "time_ringing" : time_ringing})
        time_active = self.active_queue.get(timeout=120)
        call_duration = time_active - time_ringing
        logger.info(f"call duration: {call_duration}", {"call_duration" : call_duration, "time_ringing" : time_ringing, "time_active" : time_active})
        self.mobile_atlas_mediator.hangup_call(call)
        
        self.stop_recording(ps_rec)
