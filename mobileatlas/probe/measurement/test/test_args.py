#!/usr/bin/env python3

import uuid
import argparse
from datetime import datetime
import logging
from pythonjsonlogger import jsonlogger
import json
import os
import sys
from benedict import benedict
from jsonschema import Draft7Validator, validators, ValidationError
from pathlib import Path

import pytz

class TestParser():
    # Since quectel are our default modems
    DEFAULT_MODEM_TYPE = "quectel"
    DEFAULT_LOG_DIRECTORY = "/tmp/mobileatlas/"
    DEFAULT_LOGGING_FORMAT = '%(asctime)s, %(levelname)-8s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s\r'
    DEFAULT_NETNS_DEBUGGING_PORT = 5678

    DEFAULT_TEST_NAME = "TestBase"

    CONFIG_SCHEMA_TEST = {
        "type" : "object",
        "properties" : {
            "imsi" : { "type" : "integer"},
            "phone_number" : {"type" : "string"},
            "provider_name" : {"type" : "string"},
            "test_name" : {"type": "string", "default" : DEFAULT_TEST_NAME},
            "test_params" : {"type": "object"},
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "credit_checker_name" : { "type" : "string"}    # will just default to CreditChecker_{provider_name}
                }
            }
        },
        "required": ["imsi"] #","phone_number", "provider_name"]
    }

    def __init__(self):
        self.parser = argparse.ArgumentParser(conflict_handler="resolve")
        self.validator = TestParser.extend_with_default(Draft7Validator)
        self.config_file_path = None
        self.test_args = None
        self.test_config = benedict()
        self.test_config_schemas = []
        self.startup_time = datetime.now(pytz.utc)
        self.add_arguments()

    def add_arguments(self):
        self.parser.add_argument('--modem', choices=['quectel', 'huawei', 'telit', 'simcom'],
                        default=TestParser.DEFAULT_MODEM_TYPE, help='Modem model that is used within the test environment (default: %(default)s)')
        self.parser.add_argument('--testname', default=None, help='Name of the test will be executed (default: %(default)s)')
        self.parser.add_argument('--configfile', type=argparse.FileType('r', encoding='UTF-8'), required=True)
        self.parser.add_argument('--uuid', default=uuid.uuid1(), help='Unique identifier for the test run (per default an auto-generated uuid is used))')
        self.parser.add_argument('--imsi', type=int, default=None, help="Override imsi from configfile")
        self.parser.add_argument('--debug-bridge', dest='debug_bridge', action='store_true', help='Enable virtual ethernet bridge and forward ports to allow debugging inside netns')
        self.parser.add_argument('--loglevel', dest='log_level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], default='INFO', help='Log level (default: %(default)s)')
        self.add_config_schema(TestParser.CONFIG_SCHEMA_TEST)

    def add_config_schema(self, schema):
        self.test_config_schemas.append(schema)

    def get_parser(self):
        return self.parser

    def get_args(self):
        if self.test_args is None or self.config_file_path is None:
            return ' '.join(sys.argv[1:]) # skip executable file name
        
        # get absolute path of config file
        self.config_file_path = os.path.realpath(self.test_args.configfile.name)

        # get all args and replace config filepath with absolute path
        argv_copy = [self.config_file_path if a == self.test_args.configfile.name else a for a in sys.argv]
        all_args = ' '.join(argv_copy[1:])  # skip executable file name
        # fixate uuid
        if '--uuid ' not in all_args:
            all_args = f"{all_args} --uuid {self.get_uuid()}"

        return all_args

    def parse(self):
        self.test_args, unknown = self.parser.parse_known_args()
        self.setup_logging()
        # parse config
        self.load_config(self.test_args.configfile)
        return self.test_args, self.test_config

    def load_config(self, config_file):
        try:
            self.test_config = benedict(json.load(config_file))
            self.validate_test_config()
            return self.test_config
        # error during json.load
        except ValueError as e:
            raise ValueError("Cannot parse configfile.")
        # error during jsonschema validation
        except ValidationError as e:
            raise ValueError(f"Cannot parse configfile, {e.message}.")
        finally:
            config_file.close()  # close config file

    def validate_test_config(self):
        for schema in self.test_config_schemas:
            self.validate_test_config_schema(schema)

    def validate_test_config_schema(self, schema):
        self.validator(schema).validate(self.test_config)

    def get_config(self):
        return self.test_config

    def get_modem_type(self):
        return self.test_args.modem

    def get_uuid(self):
        return self.test_args.uuid
    
    def get_imsi(self):
        # cmdline imsi overrides test config imsi
        return self.test_args.imsi or self.test_config.get('imsi', None)

    def get_phone_number(self):
        return self.test_config.get('phone_number', None)

    def get_provider_name(self):
        return self.test_config.get('provider_name', None)

    def get_test_name(self):
        # at first get it from cmdline (higher priority), otherwise get it from config
        return self.test_args.testname or self.test_config.get('test_name', TestParser.DEFAULT_TEST_NAME)

    def get_log_level(self):
        return self.test_args.log_level

    def is_debug_bridge_enabled(self):
        return self.test_args.debug_bridge

    def get_credit_checker_name(self):
        # use credit_checker from credit_checker_params, otherwise default to provider
        return self.test_config.get('credit_checker_params.credit_checker_name', None) or f"CreditChecker_{self.get_provider_name()}"

    def get_startup_time(self):
        return self.startup_time

    def setup_logging(self, log_file_name = "measurement.log"):
        #root_logger = logging.getLogger()
        #lhStdout = root_logger.handlers[0]
        #root_logger.removeHandler(lhStdout)

        path = Path(TestParser.DEFAULT_LOG_DIRECTORY)
        path.mkdir(parents=True, exist_ok=True)    #ensure the directory exists
        log_file = path / log_file_name
        json_handler = logging.FileHandler(filename=log_file, mode='w', encoding='utf-8')
        format_str = '%(asctime)s %(levelname)s %(name)s %(message)s' #'message;asctime;levelname;filename;funcName;lineno'
        formatter = jsonlogger.JsonFormatter(format_str)
        json_handler.setFormatter(formatter)
        json_handler.setLevel(logging.DEBUG)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.getLevelName(self.get_log_level()))
        console_handler.setFormatter(logging.Formatter(TestParser.DEFAULT_LOGGING_FORMAT))

        #root_logger.addHandler(json_handler)
        #root_logger.addHandler(console_handler)

        logging.basicConfig(level=logging.DEBUG, handlers=[json_handler, console_handler])
        #root_logger.info('Sign up', extra={'referral_code': '52d6ce'})

        results = logging.getLogger("RESULTS")

        """
        if json_logger is False:
            return
        


        # debug stuff
        filename = f"debug_{self.startup_time:%Y%m%d-%H%M%S}.log"
        logfile = path / filename
        json_handler = logging.FileHandler(filename=logfile, mode="a")
        json_handler.setFormatter(json_log_formatter.JSONFormatter())
        logger = logging.getLogger('MobileAtlasDebug')
        logger.addHandler(json_handler)
        logger.setLevel(logging.DEBUG)
        logger = logging.getLogger('MobileAtlasDebug')
        logger.info('Sign up', extra={'referral_code': '52d6ce'})

        filename = f"results_{self.startup_time:%Y%m%d-%H%M%S}.log"
        logfile = path / filename
        json_handler = logging.FileHandler(filename=logfile, mode="a")
        json_handler.setFormatter(json_log_formatter.JSONFormatter())
        logger = logging.getLogger('MobileAtlasResults')
        logger.addHandler(json_handler)
        logger.setLevel(logging.INFO)
        """

    # extend validator to inject default values
    # usually jsonschema just validates, see https://python-jsonschema.readthedocs.io/en/stable/faq/
    @staticmethod
    def extend_with_default(validator_class):
        validate_properties = validator_class.VALIDATORS["properties"]

        def set_defaults(validator, properties, instance, schema):
            for property, subschema in properties.items():
                if "default" in subschema:
                    instance.setdefault(property, subschema["default"])

            for error in validate_properties(
                validator, properties, instance, schema,
            ):
                yield error

        return validators.extend(
            validator_class, {"properties" : set_defaults},
        )