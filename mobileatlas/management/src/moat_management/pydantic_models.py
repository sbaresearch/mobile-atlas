import base64
import binascii
from typing import Annotated, Literal

from pydantic import BaseModel, Field, JsonValue, RootModel
from pydantic.functional_validators import AfterValidator
from pydantic.networks import IPvAnyAddress

from .models import TokenScope

MAC_RE = r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$"


def _token_validator(v: str) -> str:
    try:
        t = base64.b64decode(v, validate=True)
    except binascii.Error as e:
        raise ValueError("is invalid base64") from e

    if len(t) == 32:
        return v

    raise ValueError("must be 32 bytes long.")


def _base64_validator(v: str) -> str:
    try:
        base64.b64decode(v, validate=True)
    except binascii.Error as e:
        raise ValueError("is invalid base64") from e

    return v


TokenType = Annotated[str, AfterValidator(_token_validator)]


class RegisterReq(BaseModel):
    publickey: Annotated[str, AfterValidator(_base64_validator)]
    mac: str = Field(pattern=MAC_RE)


class WgConfig(BaseModel):
    ip: str
    endpoint: str
    endpoint_publickey: str
    allowed_ips: str
    dns: str


class TokenRegistration(BaseModel):
    token_candidate: TokenType
    mac: str = Field(pattern=MAC_RE)
    scope: TokenScope


class ActivateWgToken(BaseModel):
    scope: Literal[TokenScope.Wireguard]
    token_candidate: TokenType
    ip: IPvAnyAddress


class ActivateProbeToken(BaseModel):
    scope: Literal[TokenScope.Probe]
    token_candidate: TokenType
    name: str


class ActivateTokenAll(BaseModel):
    scope: Literal[TokenScope.Both]
    token_candidate: TokenType
    name: str
    ip: IPvAnyAddress


class ActivateToken(RootModel):
    root: ActivateWgToken | ActivateProbeToken | ActivateTokenAll = Field(
        discriminator="scope"
    )


class ChangeToken(BaseModel):
    token: TokenType
    scope: TokenScope


class Token(BaseModel):
    token: TokenType


class Mac(BaseModel):
    mac: str = Field(pattern=MAC_RE)


class Command(BaseModel):
    command: str


class Json(RootModel):
    root: JsonValue


class NetInfo(BaseModel):
    pass


class NetInfoList(RootModel):
    root: list[NetInfo]


class ChangeCountry(BaseModel):
    country: str
