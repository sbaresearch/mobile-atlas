#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import signal
import debugpy
import logging
from mobileatlas.probe.measurement.test.test_factory import test_factory
from mobileatlas.probe.measurement.credit.credit_checker_factory import credit_checker_factory
from mobileatlas.probe.measurement.test.test_args import TestParser

logger = logging.getLogger(__name__)

def main():
    print("test_executor started")

    # ignoring sighup gets us some more time to write the log etc
    # (relevant when keyboard interrupt is issued)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    
    parser = TestParser()
    parser.parse()
    logger.info("test_executor started")

    test_name = parser.get_test_name()
    if not test_factory.is_test_available(test_name):
        exit(f"Implementation for {test_name} not found.\nExiting...")
    # get an instance of the test via test-factory
    tester = test_factory.get_test(parser.get_test_name(), parser)

    #enable debugging
    if parser.is_debug_bridge_enabled():
        logger.debug("enable debug bridge...")
        tester.mobile_atlas_mediator.enable_veth_bridge()
        logger.debug("starting debugger...")
        target = debugpy.listen(("0.0.0.0", TestParser.DEFAULT_NETNS_DEBUGGING_PORT))
        logger.info(f"debugger running on {target}, wait for client")
        debugpy.wait_for_client()

    if tester.is_billing_test():
        credit_checker_name = parser.get_credit_checker_name()
        credit_checker = credit_checker_factory.get_credit_checker(credit_checker_name, tester.mobile_atlas_mediator, parser)
        tester.set_credit_checker(credit_checker)

    # everything setup, execute the test
    rc = tester.execute_test()

    logger.info(f"test_executor finished with exit code {rc}")
    exit(rc)

if __name__ == "__main__":
    main()