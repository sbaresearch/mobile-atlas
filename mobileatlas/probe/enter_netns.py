#!/usr/bin/env python3

import os
import sys
import psutil

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
        os.system(f'nsenter -t {process[0].pid} -a --wd={os.getcwd()} {command}')

    # --no-namespace option --> just execute test script without wrapping it into new ns
    else:
        os.system(command)

if __name__ == '__main__':
    main()