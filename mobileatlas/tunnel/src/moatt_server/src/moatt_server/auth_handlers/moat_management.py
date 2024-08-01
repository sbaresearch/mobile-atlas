import dataclasses
import logging
from typing import Any
from uuid import UUID

import httpx
from moatt_types.connect import Token
from pydantic import BaseModel
from pydantic.networks import AnyUrl

from ..auth_handler import AuthHandler, AuthResult, SimIdent

LOGGER = logging.getLogger(__name__)


class Settings(BaseModel):
    base_url: AnyUrl
    timeout: float = 10  # seconds
    username: str
    password: str


class MoatManagementAuth(AuthHandler):
    def __init__(self, config: dict[str, Any]):
        cfg = config.get("moat-management-auth")

        if not isinstance(cfg, dict):
            raise ValueError("moat-management-auth config is not a table.")

        self._settings = Settings(**cfg)

        self._client = httpx.AsyncClient(
            auth=httpx.BasicAuth(self._settings.username, self._settings.password),
            base_url=self._settings.base_url.unicode_string(),
            timeout=self._settings.timeout,
        )
        self._id_cache: dict[Token, UUID] = {}

        LOGGER.debug(
            "Finished initialization with the following settings: %s", self._settings
        )

    @staticmethod
    def _process_result(res: Any) -> AuthResult:
        if isinstance(res, bool) and res:
            return AuthResult.Success

        return AuthResult.Forbidden

    async def _post(self, path: str, json: Any) -> Any:
        try:
            res = await self._client.post(path, json=json)
        except Exception:
            LOGGER.exception(
                "An exception occurred while trying to communicate with the MobileAtlas management server."
            )
            raise

        match res.status_code:
            case 403:
                return AuthResult.Forbidden
            case 404:
                return AuthResult.NotFound
            case _ if not res.is_success:
                LOGGER.warning(
                    "MobileAtlas management server responded with HTTP error code: %s",
                    res.status_code,
                )
                raise AssertionError(
                    "MobileAtlas management server responded with unexpected HTTP error code."
                )

        return res.json()

    async def allowed_provider_registration(self, token: Token) -> AuthResult:
        res = await self._post("/allowed-provider-registration", token.as_base64())

        return MoatManagementAuth._process_result(res)

    async def allowed_sim_registration(
        self, token: Token, sims: list[SimIdent]
    ) -> AuthResult:
        sim_list = list(map(dataclasses.asdict, sims))
        res = await self._post(
            "/allowed-sim-registration", {"token": token.as_base64(), "sims": sim_list}
        )

        return MoatManagementAuth._process_result(res)

    async def allowed_probe_registration(self, token: Token) -> AuthResult:
        res = await self._post("/allowed-probe-registration", token.as_base64())

        return MoatManagementAuth._process_result(res)

    async def allowed_sim_request(
        self, token: Token, provider_id: UUID, sim_id: SimIdent
    ) -> AuthResult:
        res = await self._post(
            "/allowed-sim-request",
            {
                "token": token.as_base64(),
                "request": {
                    "provider_id": str(provider_id),
                    "sim": dataclasses.asdict(sim_id),
                },
            },
        )

        return MoatManagementAuth._process_result(res)

    async def identity(self, token: Token) -> UUID | None:
        if token in self._id_cache:
            return self._id_cache[token]

        res = await self._post("/identity", token.as_base64())

        if not isinstance(res, str):
            LOGGER.warning("Failed to parse MobileAtlas management server response.")
            raise ValueError("Failed to parse MobileAtlas management server response.")

        try:
            uuid = UUID(res)
        except ValueError:
            LOGGER.warning(
                "Failed to parse UUID returned by MobileAtlas management server."
            )
            raise ValueError(
                "Failed to parse UUID returned by MobileAtlas management server."
            )

        self._id_cache[token] = uuid

        return uuid
