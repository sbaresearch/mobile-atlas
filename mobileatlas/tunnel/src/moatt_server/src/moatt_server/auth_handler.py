import enum
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from moatt_types.connect import Iccid, Imsi, SessionToken

from .config import Config


@enum.unique
class AuthResult(enum.Enum):
    Success = 0
    InvalidToken = 1
    ExpiredToken = 2
    Forbidden = 3
    NotRegistered = 4


@dataclass
class SimIdents:
    id: int
    iccid: Optional[str]
    imsi: Optional[str]


class AuthHandler:
    def __init__(self, config: Config):
        ...

    async def allowed_provider_registration(self, token: SessionToken) -> AuthResult:
        raise NotImplementedError

    async def allowed_sim_registration(
        self, token: SessionToken, sims: dict[int, tuple[Iccid | None, Imsi | None]]
    ) -> AuthResult:
        raise NotImplementedError

    async def allowed_probe_registration(self, token: SessionToken) -> AuthResult:
        raise NotImplementedError

    async def allowed_sim_request(
        self, token: SessionToken, provider_id: UUID, sim_ids: SimIdents
    ) -> AuthResult:
        raise NotImplementedError

    async def identity(self, token: SessionToken) -> UUID | None:
        raise NotImplementedError


_HANDLER: AuthHandler | None = None


def init_auth_handler(handler: AuthHandler) -> None:
    global _HANDLER

    if _HANDLER is not None:
        raise AssertionError("Auth handler was already set.")

    _HANDLER = handler


def auth_handler() -> AuthHandler:
    global _HANDLER

    if _HANDLER is None:
        raise AssertionError("No auth handler set.")

    return _HANDLER
