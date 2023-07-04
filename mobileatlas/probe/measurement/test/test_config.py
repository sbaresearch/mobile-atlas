# SPDX-FileCopyrightText: 2023 MobileAtlas <https://www.mobileatlas.eu/>
#
# SPDX-License-Identifier: GPL-3.0-only

# TODO move this info into the cloud :)

class TestConfig:
    CONFIG = {
        "sims": [
            {"imsi": 232077612181881, "provider": "AT_HoT", "number" : "+4367762990392"},
            {"imsi": 232104010332590, "provider": "AT_eety", "number" : "+4366565432590"},
            #{"imsi": 232104010244834, "provider": "AT_Yess"},
            {"imsi": 232122002276350, "provider": "AT_Yesss", "number": "+4368120268977"},
            {"imsi": 232116832421357, "provider": "AT_Bob", "number" : "+436803222478"},
            {"imsi": 232033019729595, "provider": "AT_Magenta", "number" : "+436769062059"},
            {"imsi": 232056317491790, "provider": "AT_Drei", "number" : "+436605450749"},
            {"imsi": 232013730103550, "provider": "AT_A1", "number": "+4366475563550"},
            {"imsi": 232056302036592, "provider": "AT_Drei", "number": "+4369916072919"},
            {"imsi": 232170040182273, "provider": "AT_spusu", "number": "+436706082897"}
        ],
        "apns": [
            {"provider": "None"},
            {"provider": "AT_HoT", "apn": "webaut"},
            {"provider": "AT_eety", "apn": "eety.at"},
            {"provider": "AT_Yesss", "apn": "webapn.at"},
            {"provider": "AT_Drei", "apn": "drei.at"},
            {"provider": "AT_Bob", "apn": "bob.at"},
            {"provider": "AT_spusu", "apn": "mass.at"},
            {"provider": "AT_A1", "apn": "A1.net", "username": "ppp@a1plus.at", "password": "ppp"},
            {"provider": "AT_Magenta", "apn": "internet.t-mobile.at", "username": "t-mobile", "password": "tm"},
            {"provider": "AT_Magenta_Business", "apn": "business.gprsinternet", "username": "t-mobile", "password": "tm"},
            {"provider": "ES_Movistar", "apn": "movistar.es", "username": "movistar", "password": "movistar"}
        ],
        "probes" : [
            {"country" : "AT", "ip" : "10.15"},
            {"country" : "FR", "ip" : "10.14"},
            {"country" : "ES", "ip" : "10.13"},
            {"country" : "DE", "ip" : "10.12"},
            {"country" : "NL", "ip" : "10.11"},
            {"country" : "GB", "ip" : "10.10"}
        ]
    }

    @staticmethod
    def find(list, filter):
        for x in list:
            if filter(x):
                return x
        return None

    @staticmethod
    def get_apn_config(provider):
        apn_conf = TestConfig.find(TestConfig.CONFIG["apns"], lambda x: x["provider"] == provider)
        return apn_conf

    @staticmethod
    def get_network_config(imsi):
        sim = TestConfig.find(TestConfig.CONFIG["sims"], lambda x: x["imsi"] == imsi)
        if sim != None:
            provider = sim["provider"]
            apn_conf = TestConfig.find(TestConfig.CONFIG["apns"], lambda x: x["provider"] == provider)
            return apn_conf
        return None

    @staticmethod
    def get_number(imsi):
        sim = TestConfig.find(TestConfig.CONFIG["sims"], lambda x: x["imsi"] == imsi)
        if sim != None:
            return sim["number"]
        return None

    @staticmethod
    def get_probe(country):
        probe = TestConfig.find(TestConfig.CONFIG["probes"], lambda x: x["country"] == country)
        if probe != None:
            return probe["ip"]
        return None

    @staticmethod
    def get_sims():
        return TestConfig.CONFIG["sims"]

    @staticmethod
    def get_probes():
        return TestConfig.CONFIG["probes"]

    @staticmethod
    def get_country_list():
        countries = [element["country"] for element in TestConfig.CONFIG["probes"]]
        return countries

    @staticmethod
    def get_imsi_list():
        imsies = [element["imsi"] for element in TestConfig.CONFIG["sims"]]
        return imsies