#!/usr/bin/env python3
"""
SIM Modem Script ... Runs on our measurement nodes in controlled environment on Raspberry Pi
"""

# venv hack (to make it work with sudo):
import os
base_dir = os.path.dirname(os.path.abspath(__file__))
activate_this = os.path.join(base_dir, 'mobileatlas/probe/venv/bin/activate_this.py')
exec(open(activate_this).read(), {'__file__': activate_this})

import pyudev
import pexpect
import kmod
import time
from datetime import datetime
import logging
from pathlib import Path
from mobileatlas.probe.probe_args import ProbeParser
from mobileatlas.probe.tunnel.modem_tunnel import ModemTunnel

logger = logging.getLogger(__name__)

# set of modules allowed to be blacklisted
MODULES_BLACKLIST_ALLOWED = {"option", "qmi_wwan", "cdc_mbim", "cdc_wdm", "cdc_ncm", "cdc_acm", "cdc_ether", "usb_wwan",
                             "usbnet", "usbserial", "usbcore"}

MODEM_IDS = [
    (0x2c7c, 0x0125), # 4G Quectel EG25-G
    (0x2c7c, 0x0800), # 5G Quectel RM500Q
]

def blacklist_kernel_modules(module_list):
    # filter modules, only allow certain modules to be blacklisted
    module_list = MODULES_BLACKLIST_ALLOWED.intersection(module_list)

    # first blacklist modules in modprobe file
    logger.info(
        f"Create blacklist file for unwanted kernel modules: [{*module_list,}]")
    with open('/etc/modprobe.d/blacklist-mobileatlas.conf', 'w') as f:
        for mod in module_list:
            f.write(f"install {mod} /bin/false\n")

    # then remove modules in case they were already loaded
    km = kmod.Kmod()  # [(m.name, m.size) for m in km.loaded()]
    for mod in km.loaded():
        if mod.name in module_list:
            logger.info(
                f"Module {mod.name} is currently loaded but on blacklist and therefore has to be removed")
            km.rmmod(mod.name)

def wait_for_modem():
    context = pyudev.Context()
    modem_device = None
    while(not modem_device):
        for vendor_id, model_id in MODEM_IDS:
            modem_device = list(context.list_devices(subsystem="usb", ID_VENDOR_ID=vendor_id, ID_MODEL_ID=model_id)) #alternatively a more generic filter could be used?
            if modem_device:
                break
        time.sleep(1)
    
def main():
    start = datetime.utcnow()
    """
    Main script on measurement node
         1) Connect to Serial Modem and GPIO with ModemTunnel
         2) Setup Linux Network Namespace + ModemManager + NetworkManager with Magic
         3) Execute Test Script with TestWrapper
    """
    # check if executed as root, otherwise terminate with error (root is needed for namespaces, control of network interfaces etc.)
    if os.geteuid() != 0:
        exit("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")

    # parse commandline params
    parser = ProbeParser()
    try:
        parser.parse()
    except ValueError as e:
        exit(f"{e}\nExiting...")

    # block kernel modules
    blacklist_kernel_modules(parser.get_blacklisted_modules())

    # Create modem tunnel
    logger.info("setup modem tunnel...")
    tunnel = ModemTunnel(parser.get_modem_type(), parser.get_modem_adapter(), parser.get_host(), parser.get_port(), parser.get_imsi())
    tunnel.setup()  # resets modem

    logger.info("wait some time until modem is initialized...")
    wait_for_modem()
    modem_reset_time = datetime.utcnow() - start
    logger.info(f"modem was detected after {modem_reset_time.total_seconds():.2f} seconds")

    if parser.is_measurement_namespace_enabled():
        # Start ModemManager and NetworkManager and generate namespace  with Magic Script
        logger.info("create measurement namespace...")
        ps_ns = pexpect.spawn("./mobileatlas/probe/setup_measure_ns.sh")
        # give setup script some time to startup modemmanager
        ps_ns.expect('root@mobileatlas')
        # start portforwarding to netnamespace
        if parser.is_debug_bridge_enabled():
            logger.info("enable port forwarding...")
            ps_portforward = pexpect.spawn(f"socat tcp-listen:{ProbeParser.DEFAULT_NETNS_DEBUGGING_PORT},reuseaddr,fork tcp-connect:10.29.183.1:{ProbeParser.DEFAULT_NETNS_DEBUGGING_PORT}")

    # start measurements with namespace wrapper script
    ps_test = pexpect.spawn(f"./mobileatlas/probe/enter_netns.py {parser.get_test_name()} {parser.get_args()}",
                            timeout=parser.get_timeout())
    ps_test.logfile = open('/tmp/mobileatlas/ps_test.log', 'wb')
    ps_test.interact()  # invalidates timeout?!

    if parser.is_measurement_namespace_enabled():
        # exit netns process, which kills the net namespace and all processes that were running inside it
        ps_ns.sendline("exit")
        ps_ns.expect(pexpect.EOF, timeout=5)  # wait max 5 sec for process to exit

    # shutdown sim tunnel connection
    tunnel.shutdown()
    stop = datetime.utcnow()

    # simple test log
    path = Path("/etc/activities.csv")
    path.touch()
    with path.open('a') as f:
        f.write(f"0,{parser.get_test_name()},{start.isoformat(timespec='seconds')},{stop.isoformat(timespec='seconds')}")

    logger.info(f"finished (duration {stop-start}), bye!")
    exit(0)

if __name__ == "__main__":
    main()
