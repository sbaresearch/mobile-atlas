
import logging
from mobileatlas.probe.measurement.utils.format_logging import format_extra
import requests
from mobileatlas.probe.measurement.test.test_network_base import TestNetworkBase
from .payload_network_base import PayloadNetworkBase, PayloadNetworkResult

logger = logging.getLogger(__name__)

class PayloadPublicIp(PayloadNetworkBase):
    LOGGER_TAG = "payload_public_ip"

    # use http cause it might be faster and use less traffic?
    GET_IP_URL = "http://wtfismyip.com/json"

    def __init__(self, parent: TestNetworkBase, url = None):
        super().__init__(parent)
        self.parent = parent
        # url for requesting json can be specified in constructor
        self.url = url or PayloadPublicIp.GET_IP_URL
        self.tag = PayloadPublicIp.LOGGER_TAG

    def send_payload(self) -> PayloadNetworkResult:
        self.json = self.make_request(PayloadPublicIp.GET_IP_URL)
        logger.info("got public ip", extra=format_extra("dump_public_ip", {"response_json" : self.json}))
        ret = {
            'url' : self.url,
            'endpoint_ip': self.endpoint_ip,
            'endpoint_port': self.endpoint_port,
            'json_response' : self.json,
            'status_code': self.status_code
        }
        return PayloadNetworkResult(True, ret, *self.get_consumed_bytes())

    def make_request(self, url):
        # https://stackoverflow.com/questions/22492484/how-do-i-get-the-ip-address-from-a-http-request-using-the-requests-library
        resp = requests.get(url, stream=True, allow_redirects=False)
        self.endpoint_ip, self.endpoint_port = resp.raw._connection.sock.getsockname()
        logger.debug(f"resolved url {url} to {self.endpoint_ip}:{self.endpoint_port}")
        data = resp.json()
        self.status_code = resp.status_code
        return data