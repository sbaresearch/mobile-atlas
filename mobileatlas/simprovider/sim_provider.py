#!/usr/bin/env python3
"""
SIM Provider Main
"""
import os
import logging
from mobileatlas.simprovider.device_observer import DeviceEvent, DeviceObserver
from pySim.transport.serial import SerialSimLink
from pySim.transport.pcsc import PcscSimLink
from pySim.commands import SimCardCommands
from pySim.cards import SimCard



class SimInfo:
    def __init__(self, iccid, imsi, device_name, atr, sl):
        self.iccid = iccid
        self.imsi = imsi
        self.device_name = device_name
        self.atr = atr
        self.sl = sl


class SimProvider(DeviceEvent):
    TTY_SERIAL_PREFIX = "ttyUSB"

    def __init__(self):
        self.sims = []
        observer = DeviceObserver()
        observer.add_observer(self)
        observer.start()

    def device_added(self, device_type, device):
        device_name = f"{device_type}[{device}]"
        self.prepare_sim_interface(device_name, device_type, device)

    def device_removed(self, device_type, device):
        device_name = f"{device_type}[{device}]"
        self.sims = [e for e in self.sims if e.device_name != device_name]
    
    def prepare_sim_interface(self, device_name, device_type, device):
        try:
            if device_type == DeviceEvent.DEVICE_TYPE_SERIAL:
                sl = SerialSimLink(device=device)
            elif device_type == DeviceEvent.DEVICE_TYPE_SCARD:
                sl = PcscSimLink(device.index)
            sim = SimProvider.query_sim_info(device_name, sl)
            self.sims.append(sim)
        except:
            pass


    def get_sims(self):
        return self.sims

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
        sim_card = SimCard(scc) #Card(scc)

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


