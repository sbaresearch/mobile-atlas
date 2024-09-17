from base64 import b64decode, b64encode
from typing import Annotated

from pydantic import Base64Bytes, BaseModel, IPvAnyNetwork
from pydantic.functional_validators import AfterValidator


class Peer(BaseModel):
    pub_key: Base64Bytes
    allowed_ips: list[IPvAnyNetwork]


def urlsafe_b64(v: str) -> str:
    # we cant use urlsafe_b64decode here because it lacks
    # the validate parameter
    return b64encode(b64decode(v, altchars="-_", validate=True)).decode()


UrlSafeBase64 = Annotated[str, AfterValidator(urlsafe_b64)]
