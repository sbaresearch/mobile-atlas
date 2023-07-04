# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

import copy
import logging

import pytz
from mobileatlas.probe.measurement.utils.convertsizes import convert_size_to_bytes
import re
from dateutil.relativedelta import relativedelta
import requests
from benedict import benedict
from datetime import datetime
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import BillInfo, CreditChecker
from mobileatlas.probe.measurement.credit.credit_checker_web import CreditCheckerWeb
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator

logger = logging.getLogger(__name__)

class CreditChecker_AT_Magenta(CreditCheckerWeb):
    CONFIG_SCHEMA_CREDIT = {
        "type" : "object",
        "properties" : {
            "phone_number" : {"type" : "string"},
            "credit_checker_params" : {
                "type" : "object",
                "properties" : {
                    "password" : { "type" : "string"},
                },
                "required": ["password"]
            }
        },
        "required": ["phone_number", "credit_checker_params"]
    }

    # there also is another login (without csrf token):
    #https://tgate.magenta.at/oauth/non-interactive?response_type=code&scope=www&client_id=www-AEM&redirect_uri=https://www.magenta.at/bin/public/tokencheck
    """
    -----------------------------340180553028624803572881361018
    Content-Disposition: form-data; name="redirect_to"

    https://mein.t-mobile.at/myTNT/start.html
    -----------------------------340180553028624803572881361018
    Content-Disposition: form-data; name="username"

    06767xxxxxxx
    -----------------------------340180553028624803572881361018
    Content-Disposition: form-data; name="password"

    MobileAtlasPw
    -----------------------------340180553028624803572881361018
    Content-Disposition: form-data; name="j_remember_me"

    on
    -----------------------------340180553028624803572881361018
    Content-Disposition: form-data; name="submit"

    Anmelden
    -----------------------------340180553028624803572881361018--
    """

    URL_INIT = "https://mein.magenta.at" #"https://tgate.magenta.at/oauth/login"
    URL_LOGIN = "https://tgate.magenta.at/j_spring_security_check"

    URL_FREE_UNITS = "https://mein.magenta.at/myTNT/portlet.page?shortcut=freieinheiten"

    URL_JSON = "https://ca.magenta.at/ca/gwtRequest"

    PARAM_JSON = {
        "F": "at.tmobile.ca.client.process.informationdesk.proxy.factory.InformationDeskRequestFactory",
        "I": [
            {
                "O": "AIyctOPGxGy7vlZ5UF2m1GWECmA=",
                "P": [
                    "85222143"
                ]
            }
        ]
    }

    
    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser):
        super().__init__(mobile_atlas_mediator, parser)
        self.get_phone_number = parser.get_phone_number
        self.s = None
    
    def validate_credit_checker_config(self):
        super().validate_credit_checker_config()
        self.parser.validate_test_config_schema(CreditChecker_AT_Magenta.CONFIG_SCHEMA_CREDIT)

    def get_password(self):
        return self.parser.get_config().get('credit_checker_params.password', None)
    
    def get_csrf_token(self, response):
        #<input type="hidden" name="_csrf" value="c49e75d5-24bd-4a57-9f37-029330068426"/>
        res = re.search('<input type="hidden" name="_csrf" value="(.+?)"/>', response.text)
        if not res:
            res = re.search('var _csrf = "(.+?)"', response.text)
        csrf_token = res.group(1)
        return csrf_token

    def get_iframe(self, response):
        #<iframe height="650" scrolling="yes" frameborder="0" name="frmMain" id="frmMain" src="https://ca.magenta.at/ca/informationdesk.jsp?sid=2ee27d0be433d3808190cc58009eb943&CO_ID=85222143&ct=729451CEDCBD8306D8C64709F30B10024EEB5D576499E717527A9626A7ECB06FACFED68E7FB24A770107AE55219F0C094A5AD5532A10C8090315A7998CBF9275DC5CF46BD6520952839D3329CC52AAC72E2DA98D19D5CCAED461F0719B067A9F32E6649AEA7EB639245D22F0779F7F947CB7E63DD7CADAC3C06D9793B2C5B5409BF430AA6317BC78E182B4CA8BF83B5686A5D21E1ECF7A5A56EE803CDFD7E489D452987F20FA6927D5B1E7A188ACC9F8209FFDF6AF3F13151E16EC0915189193702F8C8C51DD7ABC5F3AA90AE7DD230EE4FFFC545BB51E5E8F310C04F0B48CA9BF07A36C5F0C66F8D48D7B23B1F7C35F098DCFF69BE84FB13430D630862BAED7&sp=TMAEUP_INTERN" allow="camera; microphone"></iframe>
        res = re.search('id="frmMain" src="(.+?)" allow', response.text)
        return res.group(1)

    def login_websession(self):
        logger.info("setup homepage session...")
        self.s = CreditCheckerWeb.get_requests_retry_session()
        # login
        r = self.s.get(CreditChecker_AT_Magenta.URL_INIT)
        csrf = self.get_csrf_token(r)
        param = {
            "j_username": self.get_phone_number(),
            "j_password": self.get_password(),
            "j_remember_me": "on",
            "_csrf": csrf
        }
        r = self.s.post(CreditChecker_AT_Magenta.URL_LOGIN, data=param)
        logger.info("credit_checker loggedin")

    def get_json(self):
        r = self.s.get(CreditChecker_AT_Magenta.URL_FREE_UNITS)
        url_infodesk = self.get_iframe(r)
        r = self.s.get(url_infodesk)
        csrf = self.get_csrf_token(r)
        new_header = {
            "X-CSRF-TOKEN" : csrf,
            "X-GWT-Permutation": "093406328ABD8D978D4222B23043B5C6"
        }
        self.s.headers.update(new_header)
        r = self.s.post(CreditChecker_AT_Magenta.URL_JSON, json=CreditChecker_AT_Magenta.PARAM_JSON)
        return r.json()

    # returns BillInfo
    def _retrieve_current_bill(self, new_base = False, retry = 5):
        ret = BillInfo()
        for i in range(retry+1):
            try:
                if self.s is None:
                    self.login_websession()

                resp_json = benedict(self.get_json())
                ret.bill_dump = resp_json
                resp_json = resp_json.get('O', [])
                summary = [x for x in resp_json if benedict(x).get('P.groupName') == "Daten"]
                summary = benedict(summary[0])  # contains data summary + ids of data services
                data_service_ids = summary.match('P.freeUnits[*].Y')

                data_services = [x for x in resp_json if benedict(x).get('Y') in data_service_ids]  # first is domestic data, second EU data, third is speed option
                data_services = [x for x in data_services if benedict(x).get('P.grantedUnits')] # filters out speed option

                domestic = benedict(data_services[0])
                #eu = data_services[1]
                val = domestic.get("P.appliedUnits")
                unit = domestic.get("P.uom")
                unit_byte = convert_size_to_bytes("1 " + unit)
                val_bytes = val * unit_byte

                epoch_msec = int(domestic.get("P.lastUsageDate"))
                last_used = datetime.utcfromtimestamp(epoch_msec/1000).astimezone(pytz.utc)
                
                ret.timestamp_effective_date = last_used
                ret.traffic_bytes_total = val_bytes
                if ret.traffic_bytes_total is None:
                    raise ValueError("Failed to retrieve current bill")
                else:
                    break
            except Exception:
                if i < retry:
                    self.s = None
                else:
                    raise 
        if new_base:
            self.base_bill = copy.deepcopy(ret)
        ret.subtract_base_bill(self.base_bill)
        self.current_bill = ret
        return ret