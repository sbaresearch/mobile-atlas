
import logging

import dns.resolver
from mobileatlas.probe.measurement.mediator.mobile_atlas_mediator import MobileAtlasMediator
from .payload_network_base import PayloadNetworkBase, PayloadNetworkResult

logger = logging.getLogger(__name__)


class PayloadNetworkDns(PayloadNetworkBase):
    LOGGER_TAG = "payload_network_dns"

    def __init__(self, mobile_atlas_mediator: MobileAtlasMediator, payload_size, nameservers="default"): #nameservers can also be list object
        super().__init__(mobile_atlas_mediator, payload_size=payload_size)
        self.nameservers = nameservers

    def send_payload(self) -> PayloadNetworkResult:
        cnt = 0
        my_resolver = dns.resolver.Resolver()
        if self.nameservers == "default" or self.nameservers is None:
            # do nothing and use it as it is
            logger.info(f"using default nameservers")
        if self.nameservers == "primary":
            # use only the very first dns server (that was propagated via dhcp from the provider)
            logger.info(f"using primary nameserver only")
            my_resolver._nameservers = my_resolver._nameservers[:1]
        elif isinstance(self.nameservers, list):
            logger.info(f"using specific nameservers {my_resolver._nameservers}")
            my_resolver._nameservers = self.nameservers
        logger.info(f"use nameservers {my_resolver._nameservers} for dns payload")
        while not self.is_payload_consumed(): # start over when file is fully consumed
            with open("mobileatlas/probe/measurement/payload/res/tranco_V78N.txt") as file:
                for line in file:
                    domain = line.strip()
                    cnt += 1
                    try:
                        results = my_resolver.resolve(domain, 'A', raise_on_no_answer=False)
                    except (dns.resolver.LifetimeTimeout, dns.resolver.NXDOMAIN, dns.resolver.YXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers) as e:
                        pass
                    if self.is_payload_consumed():
                        break
        return PayloadNetworkResult(True, None, *self.get_consumed_bytes(), cnt)

