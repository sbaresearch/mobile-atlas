from typing import Annotated, Optional

from pydantic import AfterValidator, BaseModel, Field, RootModel


def _digits(imsi: str) -> str:
    assert all(map(lambda b: b >= ord(b"0") and b <= ord(b"9"), imsi.encode()))
    return imsi


class Iccid(RootModel):
    root: Annotated[str, AfterValidator(_digits)] = Field(min_length=5, max_length=20)


class Imsi(RootModel):
    root: Annotated[str, AfterValidator(_digits)] = Field(min_length=5, max_length=20)


class Sim(BaseModel):
    iccid: Iccid
    imsi: Optional[Imsi]


class SimIds(RootModel):
    root: list[Iccid] = Field(min_length=1)


class SimList(RootModel):
    root: list[Sim]


class RegistrationResp(BaseModel):
    session_token: str
