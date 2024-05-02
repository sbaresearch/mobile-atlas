import dataclasses
import ipaddress
import logging
import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from ipaddress import IPv4Network, IPv6Network
from pathlib import Path
from typing import Any, TypeVar

from redis.asyncio.client import Redis

LOGGER = logging.getLogger(__name__)

ISODURATION_RE = re.compile(
    "^(?:P(?:([0-9]+)Y)?(?:([0-9]+)M)?(?:([0-9]+)W)?(?:([0-9]+)D)?)(?:T(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9]+)S)?)?$"
)


class ConfigError(Exception):
    pass


@dataclass(kw_only=True, frozen=True)
class Config:
    SERVER_HOST: str = "localhost"
    SERVER_PORT: int = 8080

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    LONG_POLLING_INTERVAL: timedelta = timedelta(seconds=60)
    NOTIFICATION_WEBHOOK: str | None = None

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    BEHIND_PROXY: bool = False

    BASIC_AUTH_USER: str
    BASIC_AUTH_PASSWORD: str

    WIREGUARD_ENDPOINT: str
    WIREGUARD_PUBLIC_KEY: str
    WIREGUARD_ALLOWED_IPS: str
    WIREGUARD_DNS: str

    ALLOWED_TUNNEL_AUTH_IPS: list[IPv4Network | IPv6Network] = field(
        default_factory=lambda: [IPv4Network("127.0.0.1"), IPv6Network("::1")]
    )

    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def redis_client(self) -> Redis:
        if (c := getattr(self, "_redis_client", None)) is not None:
            return c

        client = Redis(host=self.REDIS_HOST, port=self.REDIS_PORT)
        object.__setattr__(self, "_redis_client", client)
        return client


_CONFIG: Config | None = None


def init_config(cfg_path: Path | str | None, **cfg: Any) -> Config:
    global _CONFIG

    if _CONFIG is not None:
        raise AssertionError("Config was already initialized.")

    if cfg_path is not None:
        file_cfg = _load_config_file(cfg_path)
        cfg = file_cfg | cfg

    cfg.update(_load_env_config())

    _CONFIG = Config(**cfg)

    return _CONFIG


T = TypeVar("T")


def _set(d: dict[str, Any], k: str, v: T | None, m: Callable[[T], Any] | None = None):
    if v is not None:
        d[k] = v if m is None else m(v)


def _load_config_file(path: Path | str) -> dict[str, Any]:
    if isinstance(path, str):
        path = Path(path)

    with open(path, "rb") as f:
        cfg = tomllib.load(f)

    res: dict[str, Any] = {}
    if isinstance(server := cfg.get("server"), dict):
        _set(res, "SERVER_HOST", server.get("host"))
        _set(res, "SERVER_PORT", server.get("port"), int)
        _set(res, "BASIC_AUTH_USER", server.get("user"))
        _set(res, "BASIC_AUTH_PASSWORD", server.get("password"))
        _set(res, "BEHIND_PROXY", server.get("behind_proxy"), bool)

    if isinstance(db := cfg.get("db"), dict):
        _set(res, "DB_HOST", db.get("host"))
        _set(res, "DB_PORT", db.get("port"), int)
        _set(res, "DB_USER", db.get("user"))
        _set(res, "DB_PASSWORD", db.get("password"))
        _set(res, "DB_NAME", db.get("name"))

    if isinstance(redis := cfg.get("redis"), dict):
        _set(res, "REDIS_HOST", redis.get("host"))
        _set(res, "REDIS_PORT", redis.get("port"), int)

    if isinstance(tunnel := cfg.get("tunnel"), dict):
        if not isinstance(tunnel.get("allowed_ips"), list):
            raise ConfigError(
                'Configuration value "tunnel.allowed_ips" should be a list.'
            )

        _set(
            res,
            "ALLOWED_TUNNEL_AUTH_IPS",
            tunnel.get("allowed_ips"),
            lambda l: list(map(ipaddress.ip_network, l)),
        )

    if isinstance(probe := cfg.get("probes"), dict):
        _set(res, "LONG_POLLING_INTERVAL", probe.get("polling_interval"), _td)
        _set(res, "NOTIFICATION_WEBHOOK", probe.get("notification_webhook"))

    if isinstance(wg := cfg.get("wireguard"), dict):
        _set(res, "WIREGUARD_ENDPOINT", wg.get("endpoint"))
        _set(res, "WIREGUARD_PUBLIC_KEY", wg.get("public_key"))
        _set(res, "WIREGUARD_ALLOWED_IPS", wg.get("allowed_ips"))
        _set(res, "WIREGUARD_DNS", wg.get("dns"))

    return res


def _td(value: str) -> timedelta:
    return _parse_iso8601_duration(value.strip())


def _parse_iso8601_duration(value: str) -> timedelta:
    m = ISODURATION_RE.fullmatch(value)

    if m is None:
        raise ConfigError(f'Failed to parse "{value}" as an ISO8601 duration.')

    return timedelta(
        days=int(m.group(4)) + 365 * int(m.group(1)) + 31 * int(m.group(2)),
        weeks=int(m.group(3)),
        hours=int(m.group(5)),
        minutes=int(m.group(6)),
        seconds=int(m.group(7)),
    )


def _load_env_config() -> dict[str, Any]:
    res: dict[str, Any] = {}

    for f in dataclasses.fields(Config):
        val = os.environ.get(f.name)

        if val is None:
            continue

        t = f.type
        if t == str:
            _set(res, f.name, val)
        elif t == int:
            _set(res, f.name, val, int)
        elif t == timedelta:
            _set(res, f.name, val, _td)
        elif t == list and f.name == "ALLOWED_TUNNEL_AUTH_IPS":
            res[f.name] = list(map(ipaddress.ip_network, val.split(",")))
        else:
            raise NotImplementedError(
                f"Cant parse items of type {t}. ({f.name}: {f.type})"
            )

    return res


def get_config() -> Config:
    if _CONFIG is None:
        LOGGER.info("Config wasn't explicitly initialized. Initializing config...")
        if "MOAT-MANAGEMENT-CONFIG" not in os.environ:
            raise AssertionError(
                "Tried to initialize config but MOAT-MANAGEMENT-CONFIG env var was unset."
            )
        return init_config(os.environ["MOAT-MANAGEMENT-CONFIG"])

    return _CONFIG
