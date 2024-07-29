import pydantic_settings
from pydantic import Base64Bytes, BaseModel, IPvAnyNetwork


class Peer(BaseModel):
    pub_key: Base64Bytes
    allowed_ips: list[IPvAnyNetwork]
