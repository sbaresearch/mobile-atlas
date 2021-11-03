
from mobileatlas.probe.measurement.utils.request_utils import get_requests_retry_session
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from mobileatlas.probe.measurement.test.test_args import TestParser
from mobileatlas.probe.measurement.credit.credit_checker import CreditChecker


class CreditCheckerWeb(CreditChecker):
    def __init__(self,  mobile_atlas_mediator: MobileAtlasMediator, parser: TestParser, use_sms = False, use_call = False, use_connection = False, use_internet_gw = True):
        super().__init__(mobile_atlas_mediator, parser, use_sms = use_sms, use_call=use_call, use_connection=use_connection, use_internet_gw=use_internet_gw)
        self.s = None

    @staticmethod
    def get_requests_retry_session(
        retries=5,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        timeout=30,
        session=None,
    ):
        return get_requests_retry_session(retries, backoff_factor, status_forcelist, timeout, session)

    # https://stackoverflow.com/a/14561942
    @staticmethod
    def subtract_list_of_dict(a, b):
        a = [tuple(sorted(d.items())) for d in a]
        b = [tuple(sorted(d.items())) for d in b]
        return [dict(kvs) for kvs in set(a).difference(b)]