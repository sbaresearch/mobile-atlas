#!/usr/bin/env python3

import logging
import socket
import struct
import time
import threading

import pexpect
import serial
import RPi.GPIO as GPIO
from pySim.transport.virtual_sim import VirtualSim
from pySim.utils import b2h, h2b

logger = logging.getLogger(__name__)

class ModemTunnel(VirtualSim):
    """
    TCP Client to Connect to SIM Server
    Then simulate SIM with SerialModemLink
    """
    DEV_SERIAL = "/dev/ttyAMA1"

    # using bcm pin numbering
    PINS_MODEM_POWER_M2 = [(16, 1), (26, 0)] # pin and (default) off state
    PINS_MODEM_POWER_MPCIE = [(26, 1)] #pin and (default) off state
    PIN_SIM_RST = 5

    @staticmethod
    def get_modem_clk(modem):
        """
        Set different Modem serial clock rate ...
        Values measured with oscilloscope
           telit=3250000
           huawei=3759000
           simcom,quectel=3842000
        """
        if modem == "telit":
            return 3250000
        elif modem == "huawei":
            return 3759000
        elif modem == "simcom":
            return 3842000
        elif modem == "quectel":
            return 3842000
        else:
            raise Exception('Unknown modem')

    @staticmethod
    def get_powerup_pins(modem_adapter_type):
        if modem_adapter_type == "mpcie":
            return  ModemTunnel.PINS_MODEM_POWER_MPCIE
        elif modem_adapter_type == "m2":
            return  ModemTunnel.PINS_MODEM_POWER_M2
        return []

    def __init__(self, modem_type, adapter_type, sim_server_ip, sim_server_port, sim_imsi, rst_pin=None, do_pps=True):
        self._modem_type = modem_type
        self._clock = ModemTunnel.get_modem_clk(modem_type)
        self._sim_server_ip = sim_server_ip
        self._sim_server_port = sim_server_port
        self._sim_imsi = sim_imsi
        self._rst_pin = rst_pin
        if self._rst_pin is None:
            self._rst_pin = ModemTunnel.PIN_SIM_RST
        self._power_pins = ModemTunnel.get_powerup_pins(adapter_type)
        self._s = None  # Initialize in __init__, set in setup_connection
        self._setup_gpios()

        # bugfix for strange bug at raspi, see https://www.raspberrypi.org/forums/viewtopic.php?t=270917
        # alternatively execute 'read -t 0.1 < /dev/ttyAMA1' after startup
        with serial.Serial(ModemTunnel.DEV_SERIAL, timeout=0.01) as ser:
            ser.read()  #timeout and discard input buffer
            
        VirtualSim.__init__(self, device=ModemTunnel.DEV_SERIAL, clock=self._clock, timeout=6000, do_pps=do_pps)
        # thread should be initialized in above methode, however an error occures when we do not explicitly initialize it
        threading.Thread.__init__(self)

    def __del__(self):
        self._cleanup_gpios()

    def _cleanup_gpios(self):
        # GPIO.cleanup() # cleanup all GPIOs (sets them to imput mode)
        # disable the modem when it is not needed
        self._set_modem_power(0)

    def _setup_gpios(self):
        GPIO.setwarnings(False)  # surpress gpio already in use warning
        GPIO.setmode(GPIO.BCM)  # Broadcom pin-numbering scheme
        GPIO.setup(self._rst_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        for pin, off_state in self._power_pins:
            GPIO.setup(pin, GPIO.OUT)

    def _setup_connection(self):
        # create a socket object
        self._s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # connection to hostname on the port.
        self._s.connect((self._sim_server_ip, self._sim_server_port))
        # select imsi
        self._s.send(struct.pack('!Q', self._sim_imsi))

    def _setup_modem(self):
        """
        Modem Power Cycle and Initializiation of Modem
        """
        logger.info("setup_modem")

        # power cycle modem
        self._reset_modem()

        # start virtualsim thread
        self.start()

    def _set_modem_power(self, power_state):
        for pin, off_state in self._power_pins:
            if power_state:
                off_state = not off_state
            GPIO.output(pin, int(off_state))

    def _reset_modem(self):
        # pexpect.run("sudo ./reset-usb.sh")  #since we use the sixfab board this could be directly done via python rasp gpio
        if self._power_pins:
            self._set_modem_power(0)
            time.sleep(2)
            self._set_modem_power(1)
        else: #usb type --> power cycle usb hub :)
            pexpect.run("sudo uhubctl -a cycle")
        logger.info("modem power cycled --> listen for RST")

    def wait_for_reset(self, rst_count=2):
        for x in range(0, rst_count):
            GPIO.wait_for_edge(self._rst_pin, GPIO.RISING)
            logger.info(f"reset pin was pulled up [{x}]")

    # abstract method from virtual sim
    def handle_apdu(self, apdu):
        logger.info("forward apdu[" + str(len(apdu)) + "]: " + str(b2h(apdu)))
        self._s.send(apdu)  # forward apdu to sim-bank
        response = self._s.recv(65535)
        logger.info("recieved answer: " + str(b2h(response)))
        #self._f.write(b2h(apdu) + "- " + b2h(response) + "\n")
        return response

    def setup(self):
        #self._f = open("apdu_trace_new.txt", "w")
        self._setup_connection()
        self._setup_modem()

    def shutdown(self):
        # self._f.close()
        self._s.shutdown(socket.SHUT_RDWR)
        logger.info("shutdown -> stopping virtualsim")
        self.stop()
        logger.info("virtualsim stopped")
