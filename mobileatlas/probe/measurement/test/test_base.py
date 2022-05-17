#!/usr/bin/env python3
import logging
from mobileatlas.probe.measurement.utils.format_logging import format_extra
from mobileatlas.probe.measurement.mediator.mobile_atlas_plugin import MobileAtlasPlugin
from mobileatlas.probe.measurement.credit.credit_checker import CreditChecker
from traceback import format_exc
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.utils.git_utils import get_git_commit_hash


logger = logging.getLogger(__name__)

#when something goes wrong during a test this exceptions is thrown
class TestException(Exception):
    pass


class TestBase(MobileAtlasPlugin):
    LOGGER_TAG = "test_base"

    CONFIG_SCHEMA_TEST_BASE = {
        "type" : "object",
        "properties" : {
            "test_params" : {
                "type" : "object", 
                "properties" : {
                    "check_credit" : { "type" : "boolean"}
                }
            }
        }
    }

    def __init__(self, parser: TestParser, use_credit_checker=False):
        logger.info("creating test class...")
        self.parser = parser
        self.validate_test_config()
        super().__init__(MobileAtlasMediator(parser.get_modem_type())) #create new mediator
        self.result_logger = logging.getLogger("RESULTS")
        self.test_needs_billing_info = use_credit_checker
        self.credit_checker: CreditChecker = None
        self.rc = 1 # will be set to 0 when everything goes well

    def validate_test_config(self):
        self.parser.validate_test_config_schema(TestBase.CONFIG_SCHEMA_TEST_BASE)

    def is_billing_test(self):
        # allow overriding creditchecker via config file, otherwise make it depend on test that is executed
        return self.parser.test_config.get("test_params.check_credit", self.test_needs_billing_info)

    def set_credit_checker(self, credit_checker):
        self.credit_checker = credit_checker
    
    def add_consumed_units(self, unit_dict):
        if self.credit_checker:
            self.credit_checker.add_consumed_units(unit_dict)

    def execute_test_pre(self):
        # save commandline args and test_config file to logfile
        self.result_logger.info('dump commandline_args', extra=format_extra('dump commandline_args', {"commandline_args" : self.parser.get_args()}))
        self.result_logger.info('dump test_config', extra = format_extra('dump test_config', {"test_config": self.parser.get_config()}))
        self.result_logger.info('dump git commit',  extra = format_extra('dump git commit', {"git_hash": get_git_commit_hash()}))
        self.mobile_atlas_mediator.start()   # start glib loop
        # wait until modem is found in modemmanager
        self.mobile_atlas_mediator.wait_modem_added()
        self.mobile_atlas_mediator.wait_modem_enabled()
        self.mobile_atlas_mediator.apply_hotfixes()
        if self.is_billing_test():
            self.credit_checker.retrieve_current_bill()
        self.result_logger.info('start testbase', extra = format_extra('testbase_start'))
        self.setup_callbacks()

    def execute_test_post(self):
        self.remove_callbacks()
        if self.rc == 0:
            self.result_logger.info('stop testbase', extra = format_extra('testbase_stop'))
            if self.is_billing_test():
                # if creditchecker does not utilize the modem disable the modems radio via at-command (might speed up billing?)
                if not self.credit_checker.use_modem():
                    self.mobile_atlas_mediator.disable_rf()
                else:
                    self.mobile_atlas_mediator.toggle_rf()
                self.credit_checker.wait_for_bill()
        self.mobile_atlas_mediator.cleanup(clean_pdp_context=True)
        self.mobile_atlas_mediator.shutdown() # stop glib loop

    def execute_test_core(self):
        while True:
            cmd = input()
            if cmd == "exit":
                break

    def execute_test(self):
        try:
            self.execute_test_pre()
            self.execute_test_core()
            self.rc = 0
            logger.info("test completed successfully")
        except KeyboardInterrupt:
            logger.error("keyboard interrupt --> abort test", exc_info=True)
            self.result_logger.info('abort test', extra = format_extra('testbase_abort', {'exception':format_exc()}))
        except Exception as e:
            logger.error("exception occured --> test failed", exc_info=True)
            logger.error(f"exception: {format_exc()}")
            self.result_logger.info('exception during test', extra = format_extra('testbase_abort', {'exception':format_exc()}))
        finally:
            self.execute_test_post()
        return self.rc

