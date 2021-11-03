
import logging
from mobileatlas.probe.measurement.credit.credit_checker import CreditChecker
from mobileatlas.probe.measurement.utils.format_logging import format_extra
import requests
from urllib.parse import urlparse
from urllib3.exceptions import InsecureRequestWarning

from mobileatlas.probe.measurement.utils.resolv_utils import _get_ip, _bind_ip, _fix_ip, _remove_binding
from mobileatlas.probe.measurement.utils.quic import QuicWrapper

from mobileatlas.probe.measurement.test.test_network_base import TestNetworkBase
from .payload_network_base import PayloadNetworkBase, PayloadNetworkResult

logger = logging.getLogger(__name__)

class PayloadNetworkWebResult(PayloadNetworkResult):
    def __init__(self, success, result, consumed_bytes_rx, consumed_bytes_tx, request_cnt):
        self.success = success
        self.result = result
        self.consumed_bytes_rx = consumed_bytes_rx
        self.consumed_bytes_tx = consumed_bytes_tx
        self.request_cnt = request_cnt

class PayloadNetworkWeb(PayloadNetworkBase):
    LOGGER_TAG = "payload_network_web"
    ALLOWED_PROTOCOLS = ["https", "http", "quic"]

    def __init__(self, parent: TestNetworkBase, payload_size, url, force_protocol=None, repetitive_dns = False, allow_redirects=False, fix_target_ip = None, override_sni_host=None):
        super().__init__(parent, payload_size=payload_size)
        self.parent = parent
        if force_protocol and force_protocol not in PayloadNetworkWeb.ALLOWED_PROTOCOLS:
            raise ValueError()
        self.force_protocol = force_protocol
        self.evade_dns = not repetitive_dns
        self.allow_redirects = allow_redirects
        self.fix_target_ip = fix_target_ip
        self.override_sni_host = override_sni_host
        self.tag = PayloadNetworkWeb.LOGGER_TAG
        self.fail_cnt = 0
        self.url = urlparse(url)
        self.url = self.url._replace(scheme=self.get_scheme())    #only replace if forced, otherwise just use whats provided (or https on default)

    def get_scheme(self):
        protocol = self.get_protocol()
        scheme = 'https' if protocol == 'quic' else protocol    #return protocol or https if protocol is quic
        return scheme

    def get_request_url(self):
        request_url = self.url
        if self.override_sni_host:
            old_hostname = request_url.hostname
            new_hostname = self.override_sni_host
            request_url = request_url._replace(netloc=request_url.netloc.replace(old_hostname, new_hostname)) #hostname cannot be replaced directly, therefore we need this little hack with netloc
        return request_url
    
    def get_target_ip(self):
        return self.fix_target_ip or _get_ip(self.url.hostname)

    def get_protocol(self):
        return self.force_protocol or self.url.scheme or 'https' #use replacement protocol, otherwise protocol from link, otherwise just default to https (to get a link that is accepted by requests)

    def get_port(self):
        return self.url.port or 80 if self.url.scheme == 'http' else 443

    def get_verify_ssl(self):
        return not (self.fix_target_ip or self.override_sni_host)   #disable ssl verification when one of those is set

    def manage_ip_binding(self, status):
        if (self.fix_target_ip or self.override_sni_host) and status == "start":
            # Suppress only the single warning from urllib3 needed.
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
            logger.debug(f"fix hostname {self.url.hostname} to ip {self.fix_target_ip} on port {self.get_port()}")
            _bind_ip(self.get_request_url().hostname, self.get_port(), self.get_target_ip()) 
        elif self.evade_dns and status == "start":
            logger.debug(f"add resolve-bingung for {self.url.hostname} on port {self.get_port()}")
            _fix_ip(self.url.hostname, self.get_port())
        elif (self.evade_dns or self.target_ip) and status == "stop":
            logger.debug(f"remove resolv-bindung for hostname {self.url.hostname} on port {self.get_port()}")
            _remove_binding(self.get_request_url().hostname, self.get_port())

    def send_payload(self) -> PayloadNetworkResult:
        success = True
        self.manage_ip_binding("start")
        logger.info(f"send_payload, sending {self.payload_size} bytes to {self.url.geturl()}, use protocol {self.get_protocol()}")
        i = 0
        while not self.is_payload_consumed():
            i += 1
            self.make_request()
            if self.fail_cnt > 3:
                success = False
                break
        self.manage_ip_binding("stop")
        return PayloadNetworkWebResult(success, None, *self.get_consumed_bytes(), i)

    def make_request(self):
        url = self.get_request_url().geturl()
        try:
            if self.get_protocol() == 'quic':
                resp = QuicWrapper().request(url)
            else:
                resp = requests.get(url, allow_redirects=self.allow_redirects, verify=self.get_verify_ssl(), timeout=15)
            self.fail_cnt = 0
            return True
        except Exception as error:
            logging.exception(error)
            self.fail_cnt += 1
            return False



class PayloadNetworkWebControlTraffic(PayloadNetworkWeb):
        BYTES_MAX = 10 * CreditChecker.MEGABYTE
        BYTES_MIN = 10 * CreditChecker.KILOBYTE

        BASE_URLS = {
            "http" : "http://httpbin.org/bytes/",
            "https": "https://httpbin.org/bytes/",
            "quic": "https://quic.aiortc.org/httpbin/bytes/"
        }
        #def __init__(self, parent: TestNetworkBase, payload_size, url, force_protocol=None, repetitive_dns = False, allow_redirects=False, fix_target_ip = None):
        def __init__(self, parent: TestNetworkBase, payload_size, protocol, request_size = None):
            self.request_size = request_size
            if protocol not in PayloadNetworkWeb.ALLOWED_PROTOCOLS:
                raise ValueError()
            self.base_url = PayloadNetworkWebControlTraffic.BASE_URLS.get(protocol)
            super().__init__(parent, payload_size=payload_size, url=self.base_url, force_protocol = protocol)

        def get_request_size(self):
            if self.request_size:
                return self.request_size
            missing_bytes = self.get_missing_bytes()
            current = PayloadNetworkWebControlTraffic.BYTES_MAX
            while current > missing_bytes:
                if missing_bytes <= PayloadNetworkWebControlTraffic.BYTES_MIN:
                    return PayloadNetworkWebControlTraffic.BYTES_MIN
                current /=2
            return int(current)

        def make_request(self):
            # get missing bytes and set url
            self.url = urlparse(f"{self.base_url}{self.get_request_size()}")
            super().make_request()