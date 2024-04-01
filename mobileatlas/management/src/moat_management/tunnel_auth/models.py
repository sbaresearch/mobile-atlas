import enum
from typing import Annotated, Optional
from uuid import UUID

from pydantic import (
    AfterValidator,
    Base64Bytes,
    BaseModel,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

from .. import models as dbm


@enum.unique
class AuthError(enum.Enum):
    InvalidToken = 1
    ExpiredToken = 2
    Forbidden = 3


class AuthException(Exception):
    def __init__(self, error: AuthError):
        self.error = error


class Token(RootModel):
    root: Base64Bytes


def _digits(imsi: str) -> str:
    if not all(map(lambda b: b >= ord(b"0") and b <= ord(b"9"), imsi.encode())):
        raise ValueError

    return imsi


DigitStr = Annotated[str, AfterValidator(_digits)]


class Iccid(RootModel):
    root: DigitStr = Field(min_length=5, max_length=20)


class Imsi(RootModel):
    root: DigitStr = Field(min_length=5, max_length=20)


class SimId(BaseModel):
    id: int = Field(ge=0, lt=2**64)
    iccid: Optional[Iccid] = None
    imsi: Optional[Imsi] = None

    @model_validator(mode="after")
    def require_id(self):
        if self.iccid is None and self.imsi is None:
            raise ValueError

        return self


class SimList(RootModel):
    root: list[SimId]

    @field_validator("root")
    @classmethod
    def no_duplicate_ids(cls, sims: list[SimId]) -> list[SimId]:
        iccids = [s.iccid.root for s in sims if s.iccid is not None]
        imsis = [s.imsi.root for s in sims if s.imsi is not None]

        if len(set(iccids)) != len(iccids) or len(set(imsis)) != len(imsis):
            raise ValueError

        return sims


class SimRequest(BaseModel):
    provider_id: UUID
    sim: SimId


class TunnelRegistration(BaseModel):
    token: Base64Bytes


class TunnelRegResponse(BaseModel):
    session_token: Base64Bytes


class TokenCreation(BaseModel):
    admin: bool
    scope: dbm.MoAtTokenScope


class AllowSim(BaseModel):
    iccid: Optional[Iccid] = None
    imsi: Optional[Imsi] = None
    public: bool
    provide: bool
    request: bool

    @model_validator(mode="after")
    def require_id(self):
        if self.iccid is None and self.imsi is None:
            raise ValueError

        return self
