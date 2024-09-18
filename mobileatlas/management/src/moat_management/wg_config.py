import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import TracebackType

import httpx

LOGGER = logging.getLogger(__name__)


class WgConfigError(Exception):
    pass


class WgConfig:
    def __init__(self, url: str):
        self._url: str = url
        self._client: httpx.AsyncClient | None = None

    async def add_peer(self, publickey: str, ip: str) -> None:
        """Adds a new peer to the wireguard configuration."""

        client = self._check_initialized()

        r = await client.put("/peers", json={"pub_key": publickey, "allowed_ips": [ip]})
        self._check_response(r)

    async def status(self) -> str:
        """Retrieves the current wireguard configuration."""

        client = self._check_initialized()

        r = await client.get("/status")
        self._check_response(r)

        json = r.json()

        if not isinstance(json, str):
            LOGGER.warning("wg-daemon did not return the wg status as a JSON string.")
            raise WgConfigError

        return json

    async def remove_peer(self, publickey: str) -> None:
        """Removes a peer from wireguard."""

        client = self._check_initialized()

        urlsafe_pk = publickey.translate(str.maketrans("+/", "-_"))
        r = await client.delete(f"/peers/{urlsafe_pk}")
        self._check_response(r)

    def _check_initialized(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "WgConfig was not initialized. Please use this class as an async context manager."
            )

        return self._client

    def _check_response(self, response: httpx.Response) -> None:
        if not response.is_success:
            LOGGER.warning(
                "Wireguard service returned non success status (%d):\n%s",
                response.status_code,
                response.content,
            )
            raise WgConfigError

    async def __aenter__(self):
        if self._client is not None:
            raise RuntimeError("Cannot open WgConfig more than once.")

        if self._url.startswith("unix:"):
            transport = httpx.AsyncHTTPTransport(uds=self._url.removeprefix("unix:"))

            client = httpx.AsyncClient(transport=transport, base_url="http://wg-daemon")
        else:
            client = httpx.AsyncClient(base_url=self._url)

        self._client = await client.__aenter__()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.__aexit__(exc_type, exc_value, traceback)
            self._client = None


_WG_CONFIG: WgConfig | None = None


@asynccontextmanager
async def wg_config(url) -> AsyncGenerator[WgConfig, None]:
    global _WG_CONFIG

    async with WgConfig(url) as c:
        _WG_CONFIG = c
        yield c


def get_wg_config() -> WgConfig:
    global _WG_CONFIG

    if _WG_CONFIG is None:
        raise RuntimeError("Connection to wireguard daemon was not initialized.")

    return _WG_CONFIG
