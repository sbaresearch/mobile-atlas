from typing import Annotated, Optional

import moatt_types.connect as mtc
from pydantic import AfterValidator, BaseModel, Field, RootModel, field_validator


def _digits(imsi: str) -> str:
    if not all(map(lambda b: b >= ord(b"0") and b <= ord(b"9"), imsi.encode())):
        raise ValueError

    return imsi


DigitStr = Annotated[str, AfterValidator(_digits)]


class Iccid(RootModel):
    root: DigitStr = Field(min_length=5, max_length=20)

    def as_iccid(self) -> mtc.Iccid:
        return mtc.Iccid(self.root)


class Imsi(RootModel):
    root: DigitStr = Field(min_length=5, max_length=20)

    def as_imsi(self) -> mtc.Imsi:
        return mtc.Imsi(self.root)


class Sim(BaseModel):
    id: int = Field(ge=0, lt=2**64)
    iccid: Optional[Iccid] = None
    imsi: Optional[Imsi] = None

    def get_iccid(self) -> mtc.Iccid | None:
        if self.iccid is None:
            return None

        return self.iccid.as_iccid()

    def get_imsi(self) -> mtc.Imsi | None:
        if self.imsi is None:
            return None

        return self.imsi.as_imsi()


class SimList(RootModel):
    root: list[Sim]

    @field_validator("root")
    @classmethod
    def no_duplicate_ids(cls, sims: list[Sim]) -> list[Sim]:
        iccids = [s.iccid.root for s in sims if s.iccid is not None]
        imsis = [s.imsi.root for s in sims if s.imsi is not None]

        if len(set(iccids)) != len(iccids) or len(set(imsis)) != len(imsis):
            raise ValueError

        return sims


class RegistrationResp(BaseModel):
    session_token: str
