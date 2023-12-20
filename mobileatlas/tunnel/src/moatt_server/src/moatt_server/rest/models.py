from typing import Annotated, Callable

from pydantic import AfterValidator, BaseModel, RootModel


def _digits(imsi: str) -> str:
    assert all(map(lambda b: b >= ord(b"0") and b <= ord(b"9"), imsi.encode()))
    return imsi


def _len(min: int, max: int) -> Callable[[str], str]:
    def f(i: str):
        assert len(i) >= min and len(i) <= max
        return i

    return f


class Sim(BaseModel):
    iccid: Annotated[str, AfterValidator(_digits), AfterValidator(_len(5, 20))]
    imsi: Annotated[str, AfterValidator(_digits), AfterValidator(_len(5, 15))]


class SimList(RootModel):
    root: list[Sim]


class RegistrationResp(BaseModel):
    session_token: str
