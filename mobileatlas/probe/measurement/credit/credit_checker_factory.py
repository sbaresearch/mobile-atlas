#!/usr/bin/env python3


from mobileatlas.probe.measurement.credit.credit_checker import CreditChecker

#RO
from mobileatlas.probe.measurement.credit.ro.ro_telekom import CreditChecker_RO_Telekom
from mobileatlas.probe.measurement.credit.ro.ro_vodafone import CreditChecker_RO_Vodafone
from mobileatlas.probe.measurement.credit.ro.ro_orange import CreditChecker_RO_Orange

#AT
from mobileatlas.probe.measurement.credit.at.at_a1 import CreditChecker_AT_A1
from mobileatlas.probe.measurement.credit.at.at_magenta import CreditChecker_AT_Magenta
from mobileatlas.probe.measurement.credit.at.at_eety import CreditChecker_AT_eety
from mobileatlas.probe.measurement.credit.at.at_hot import CreditChecker_AT_HoT
from mobileatlas.probe.measurement.credit.at.at_yesss import CreditChecker_AT_yesss
from mobileatlas.probe.measurement.credit.at.at_spusu import CreditChecker_AT_spusu
from mobileatlas.probe.measurement.credit.at.at_drei import CreditChecker_AT_Drei

#HR
from mobileatlas.probe.measurement.credit.hr.hr_a1 import CreditChecker_HR_A1
from mobileatlas.probe.measurement.credit.hr.hr_telekom import CreditChecker_HR_Telekom
from mobileatlas.probe.measurement.credit.hr.hr_telemach import CreditChecker_HR_Telemach

#SK
from mobileatlas.probe.measurement.credit.sk.sk_o2 import CreditChecker_SK_O2
from mobileatlas.probe.measurement.credit.sk.sk_orange import CreditChecker_SK_Orange

class CreditCheckerFactory:
    def __init__(self):
        self._creators = {}

    def register_credit_checker(self, credit_checker, creator):
        self._creators[credit_checker] = creator

    def get_credit_checker(self, credit_checker, mediator, parser) -> CreditChecker:
        creator = self._creators.get(credit_checker)
        if not creator:
            raise ValueError(credit_checker)
        return creator(mediator, parser)

    def is_credit_checker_available(self, credit_checker):
        return self._creators.get(credit_checker) is not None


credit_checker_factory = CreditCheckerFactory()
#AT
credit_checker_factory.register_credit_checker('CreditChecker_AT_A1', CreditChecker_AT_A1)
credit_checker_factory.register_credit_checker('CreditChecker_AT_Magenta', CreditChecker_AT_Magenta)
credit_checker_factory.register_credit_checker('CreditChecker_AT_Drei', CreditChecker_AT_Drei)
credit_checker_factory.register_credit_checker('CreditChecker_AT_spusu', CreditChecker_AT_spusu)
credit_checker_factory.register_credit_checker('CreditChecker_AT_yesss', CreditChecker_AT_yesss)
credit_checker_factory.register_credit_checker('CreditChecker_AT_HoT', CreditChecker_AT_HoT)
credit_checker_factory.register_credit_checker('CreditChecker_AT_eety', CreditChecker_AT_eety)

#HR
credit_checker_factory.register_credit_checker('CreditChecker_HR_A1', CreditChecker_HR_A1)
credit_checker_factory.register_credit_checker('CreditChecker_HR_Telekom', CreditChecker_HR_Telekom)
credit_checker_factory.register_credit_checker('CreditChecker_HR_Telemach', CreditChecker_HR_Telemach)

#RO
credit_checker_factory.register_credit_checker('CreditChecker_RO_Vodafone', CreditChecker_RO_Vodafone)
credit_checker_factory.register_credit_checker('CreditChecker_RO_Telekom', CreditChecker_RO_Telekom)
credit_checker_factory.register_credit_checker('CreditChecker_RO_Orange', CreditChecker_RO_Orange)

#SK
credit_checker_factory.register_credit_checker('CreditChecker_SK_O2', CreditChecker_SK_O2)
credit_checker_factory.register_credit_checker('CreditChecker_SK_Orange', CreditChecker_SK_Orange)