#!/usr/bin/env python3
"""
SIM Provider Main
"""
import os
import logging
import re
import argparse
import json
import serial
import requests
from serial.tools import list_ports
from smartcard.System import readers
from pySim.transport.serial import SerialSimLink
from pySim.transport.pcsc import PcscSimLink
from pySim.commands import SimCardCommands
from pySim.cards import Card



class SimInfo:
    def __init__(self, iccid, imsi, device_name, atr, sl):
        self.iccid = iccid
        self.imsi = imsi
        self.device_name = device_name
        self.atr = atr
        self.sl = sl


class SimProvider():
    TTY_SERIAL_PREFIX = "ttyUSB"

    def __init__(self):
        pass
        
    def get_tty_devices(self, prefix):
        """
        Return a list of all ttyUSB devices, our potential SIM Readers with pyserial
        """
        simports = []
        for elem in list_ports.grep(prefix):
            simports.append(elem.device)
        simports.sort()
        return simports

    def get_serial_sims(self):
        serial_sims = []
        tty_devices = self.get_tty_devices(SimProvider.TTY_SERIAL_PREFIX)

        for tty in tty_devices:
            if not SimProvider.check_permissions(tty):
                logging.warning(f"Device {tty} has unsufficient permissions")
                continue

            sl = SerialSimLink(device=tty)
            device_name = f"Serial: {tty}"
            sim = SimProvider.query_sim_info(device_name, sl)
            if sim:
                serial_sims.append(sim)
        return serial_sims

    
    def get_pcsc_sims(self):
        pcsc_sims = []
        for index, reader in enumerate(readers()):
            try:
                sl = PcscSimLink(index)
                device_name = f"PC/SC[{index}]: {reader}"
                sim = SimProvider.query_sim_info(device_name, sl)
                if sim:
                    pcsc_sims.append(sim)
            except:
                logging.warning(f"exception reading pcsc device[{index}]: {reader}")
                pass
        return pcsc_sims

    def get_sims(self):
        serial_sims = self.get_serial_sims()
        pcsc_sims = self.get_pcsc_sims()
        # TODO: add other sim provider types (e.g. bluetooth, modem_at, etc.)
        sims = serial_sims + pcsc_sims
        return sims

    @staticmethod
    def check_permissions(tty_device):
        """
        Check if we have Read and Write Permission on file
        """
        return os.access(tty_device, os.R_OK) and os.access(tty_device, os.W_OK)

    @staticmethod
    def query_sim_info(device_name, sl, is_connected=False):
        """
        Retrieve sim info
        """
        # connect simlink if not connected
        if not is_connected:
            sl.connect()

        # Create command layer
        scc = SimCardCommands(transport=sl)

        # TODO: add check that it is an actual sim card?
        sim_card = Card(scc) #SimCard(scc)

        # query iccid
        iccid, sw = sim_card.read_iccid()
        if not iccid or sw != '9000':
            logging.debug(f"Error querying iccid ({iccid}, {sw})")
            return None

        # query imsi
        imsi, sw = sim_card.read_imsi()
        if not imsi:
            logging.debug(f"Error querying imsi ({imsi}, {sw})")
            return None

        sim_info = SimInfo(iccid, imsi, device_name, sl.get_atr(), sl)

        # bring back into disconnected state
        if not is_connected:
             sl.disconnect()

        logging.info(f"device {sim_info.device_name} --> has imsi {sim_info.imsi}, iccid {sim_info.iccid}, and atr {sim_info.atr}")

        return sim_info


