import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from moatt_types.connect import Token


@enum.unique
class AuthResult(enum.Enum):
    Success = 0
    InvalidToken = 1
    ExpiredToken = 2
    Forbidden = 3
    NotRegistered = 4
    NotFound = 5


@dataclass
class SimIdent:
    id: int
    iccid: Optional[str]
    imsi: Optional[str]


class AuthHandler(ABC):
    def __init__(self, config: dict[str, Any] | None):
        pass

    @abstractmethod
    async def allowed_provider_registration(self, token: Token) -> AuthResult: ...

    @abstractmethod
    async def allowed_sim_registration(
        self,
        token: Token,
        sims: list[SimIdent],
    ) -> AuthResult: ...

    @abstractmethod
    async def allowed_probe_registration(self, token: Token) -> AuthResult: ...

    @abstractmethod
    async def allowed_sim_request(
        self, token: Token, provider_id: UUID, sim_id: SimIdent
    ) -> AuthResult: ...

    @abstractmethod
    async def identity(self, token: Token) -> UUID | None: ...
