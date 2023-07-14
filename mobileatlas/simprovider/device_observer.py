#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import os
import logging
from threading import Event, Thread
from serial.tools import list_ports
from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.System import readers

class Observer(Thread):
    def __init__(self, sleeping_time):
        super().__init__()
        self.stop_event = Event()
        self.sleeping_time = sleeping_time

    def observe():
        raise NotImplementedError()

    def run(self):
        while not self.stop_event.wait(self.sleeping_time):
            self.observe()

    def stop(self):
        self.stop_event.set()


class DeviceEvent:
    DEVICE_TYPE_SERIAL = "Serial"
    DEVICE_TYPE_SCARD = "PC/SC"

    def device_added(self, device_type, device):
        raise NotImplementedError

    def device_removed(self, device_type, device):
        raise NotImplementedError


class SerialObserver(Observer):
    SLEEPING_TIME = 1
    DEVICE_TYPE = DeviceEvent.DEVICE_TYPE_SERIAL

    def __init__(self):
        super().__init__(SerialObserver.SLEEPING_TIME)
        self.current_devices = []
        self.listener = []
        self.devices_permission_warning = []


    @staticmethod
    def check_permissions(tty_device):
        """
        Check if we have Read and Write Permission on file
        """
        return os.access(tty_device, os.R_OK) and os.access(tty_device, os.W_OK)

    def observe(self):
        try:
            current = self.current_devices.copy()
            for s in list_ports.comports():
                device = s.device
                has_permission = SerialObserver.check_permissions(device)
                if device not in current and has_permission:
                    #notify new device
                    self.current_devices.append(device)
                    self.notify_add(SerialObserver.DEVICE_TYPE, device)
                elif device in current:
                    current.remove(device)
                elif not has_permission and device not in self.devices_permission_warning:
                    self.devices_permission_warning.append(device)
                    logging.warning(f"Device {device} has unsufficient permissions")

            # devices that remain in current were removed
            for removed in current:
                self.current_devices.remove(removed)
                if removed in self.devices_permission_warning: self.devices_permission_warning.remove(removed)
                self.notify_remove(SerialObserver.DEVICE_TYPE, removed)
        except Exception as e:
            logging.error('Exception '+ repr(e))

    def notify_add(self, device_type, device):
        for l in self.listener:
            l.device_added(device_type, device)
    
    def notify_remove(self, device_type, device):
        for l in self.listener:
            l.device_removed(device_type, device)

    def add_observer(self, obj):
        self.listener.append(obj)

    def remove_observer(self, obj):
        self.listener.remove(obj)




class DeviceObserver(SerialObserver, CardObserver):
    def __init__(self):
        super().__init__()
        self.cardmonitor = CardMonitor()

    def start(self):
        self.cardmonitor.addObserver(self)
        super().start()
    
    def stop(self):
        self.cardmonitor.deleteObserver(self)
        super().stop()
        #self.join()

    # callback from cardobserver --> convert to notifications
    def update(self, observable, actions):
        (addedcards, removedcards) = actions
        for card in addedcards:
            self.notify_add(DeviceEvent.DEVICE_TYPE_SCARD, DeviceObserver.get_scard_reader(card.reader))
        for card in removedcards:
            self.notify_remove(DeviceEvent.DEVICE_TYPE_SCARD, DeviceObserver.get_scard_reader(card.reader))

    @staticmethod
    def get_scard_reader(device):   # basically same as https://github.com/LudovicRousseau/pyscard/blob/master/smartcard/Card.py#L65
        if type(device) == str:
            for i, reader in enumerate(readers()):
                if device == str(reader):
                    reader.index = i
                    return reader
        else:
            return device


class TestListener(DeviceEvent):
    def device_added(self, device_type, device):
        logging.info(f"Added {device_type} device: {device}")

    def device_removed(self, device_type, device):
        logging.info(f"Removed {device_type} device: {device}")

import time
if __name__ == '__main__':
    observer = DeviceObserver()
    listener = TestListener()
    observer.add_observer(listener)

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()