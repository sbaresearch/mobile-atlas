#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import os
import sys
import psutil
import pexpect

modem_interface = "wwan0"
measurement_ns = "ns_mobileatlas"
timeout = 60*60*24*7 # -1 does not work >.<

def move_modem_to_ns(x):
    if psutil.net_io_counters(True).get(modem_interface): #use counters because psutil.net_if_addrs() doesn't show wwan0 when it is down :X
        print("move wwan to measurement namespace...")
        pexpect.run(f"ip link set {modem_interface} netns {measurement_ns}")

def main():
    enter_namespace = '--no-namespace' not in sys.argv
    forward_args = ' '.join(sys.argv[1:]) # add namespace arg
    command = f'python3 -m mobileatlas.probe.measurement.test_executor {forward_args}'

    # get namespace from process manager and start test within namespace
    if enter_namespace:
        # Get the current PID of ModemManager (which runs in separate Namespace)
        process = [proc for proc in psutil.process_iter() if proc.name()
                == 'ModemManager']

        # If no ModemManager is running, quit with error
        if len(process) != 1:
            sys.exit('modemmanager not running -> exit...')

        # Execute nsenter to switch all namespaces (incl. network namespace) into ModemManager namespace
        #    and execute testscript with python3
        cmd = f'nsenter -t {process[0].pid} -n -m -p --wd={os.getcwd()} {command}'
        pexpect.run(cmd, timeout=timeout, logfile=sys.stdout.buffer, events={':nm_modem_added:':move_modem_to_ns})

    # --no-namespace option --> just execute test script without wrapping it into new ns
    else:
        pexpect.run(command, timeout=timeout)
    print("wrapper enter_ns finished")

if __name__ == '__main__':
    main()
