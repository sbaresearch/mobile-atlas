import dataclasses
import importlib
import logging
import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

from .auth_handler import AuthHandler
from .auth_handlers import MoatManagementAuth

LOGGER = logging.getLogger(__name__)
ISODURATION_RE = re.compile(
    "^(?:P(?:([0-9]+)Y)?(?:([0-9]+)M)?(?:([0-9]+)W)?(?:([0-9]+)D)?)(?:T(?:([0-9]+)H)?(?:([0-9]+)M)?(?:([0-9]+)S)?)?$"
)


# TODO: find sensible defaults
@dataclass(kw_only=True, frozen=True)
class Config:
    AUTHMSG_TIMEOUT: Optional[timedelta] = timedelta(minutes=10)
    PROVIDER_RESPONSE_TIMEOUT: Optional[timedelta] = timedelta(minutes=10)
    PROVIDER_EXPIRATION: Optional[timedelta] = timedelta(minutes=10)
    PROBE_REQUEST_TIMEOUT: Optional[timedelta] = timedelta(minutes=10)
    TCP_KEEPIDLE: Optional[timedelta] = timedelta(minutes=10)
    TCP_KEEPINTVL: Optional[timedelta] = timedelta(minutes=10)
    TCP_KEEPCNT: Optional[int] = 10
    TCP_KEEPALIVE: bool = True
    MAX_QUEUE_SIZE: int = 10
    MAX_PROBE_WAITTIME: Optional[timedelta] = timedelta(minutes=5)

    GC_INTERVAL: timedelta = timedelta(minutes=1)
    QUEUE_GC_INTERVAL: timedelta = timedelta(minutes=1)

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    # TODO allow setting via config (instead of only through cmdline args)
    # TUNNEL_PORT: int = 6666
    # TUNNEL_CERT: str = "ssl/server.crt"
    # TUNNEL_CERT_KEY: str = "ssl/server.key"

    AUTH_HANDLER: AuthHandler

    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


class ConfigError(Exception):
    pass


def _set(
    d: dict[str, Any],
    name: str,
    value: Optional[Any],
    mapper: Callable[[Any], Any] | None = None,
) -> None:
    if value is not None:
        d[name] = value if mapper is None else mapper(value)


def _opt_td(value: str) -> timedelta | None:
    if value == "":
        return None

    return _parse_iso8601_duration(value.strip())


def _td(value: str) -> timedelta:
    return _parse_iso8601_duration(value.strip())


def _parse_iso8601_duration(value: str) -> timedelta:
    m = ISODURATION_RE.fullmatch(value)

    if m is None:
        raise ConfigError

    return timedelta(
        days=int(m.group(4)) + 365 * int(m.group(1)) + 31 * int(m.group(2)),
        weeks=int(m.group(3)),
        hours=int(m.group(5)),
        minutes=int(m.group(6)),
        seconds=int(m.group(7)),
    )


# TODO: test loading of arbitrary classes
def _load_handler(
    cls: str, cfg: dict[str, Any], allow_plugins: bool = False
) -> AuthHandler:
    match cls:
        case "moat-management":
            return MoatManagementAuth(cfg)
        case _:
            if not allow_plugins:
                raise ConfigError(f'Unknown auth handler: "{cls}".')

    module_name, class_name = cls.split(":")
    m = importlib.import_module(module_name)
    c = getattr(m, class_name)

    if not issubclass(c, AuthHandler):
        raise ConfigError(
            "Loading of auth handler failed. Not a subclass of AuthHandler."
        )

    return c(cfg)


def _load_toml_config(
    cfg: dict[str, Any], module_loading_allowed: bool = False
) -> Optional[dict[str, Any]]:

    res = {}

    if isinstance(db := cfg.get("db"), dict):
        _set(res, "DB_HOST", db.get("host"))
        _set(res, "DB_PORT", db.get("port"))
        _set(res, "DB_USER", db.get("user"))
        _set(res, "DB_NAME", db.get("name"))
        _set(res, "DB_PASSWORD", db.get("password"))

    if isinstance(timeouts := cfg.get("timeouts"), dict):
        _set(res, "AUTHMSG_TIMEOUT", timeouts.get("authmsg"), _opt_td)
        _set(
            res, "PROVIDER_RESPONSE_TIMEOUT", timeouts.get("provider_response"), _opt_td
        )
        _set(
            res,
            "PROVIDER_EXPIRATION",
            timeouts.get("provider_expiration"),
            _opt_td,
        )
        _set(res, "PROBE_REQUEST_TIMEOUT", timeouts.get("probe_request"), _opt_td)
        _set(res, "TCP_KEEPIDLE", timeouts.get("keepidle"), _opt_td)
        _set(res, "TCP_KEEPINTVL", timeouts.get("keepintvl"), _opt_td)
        _set(
            res,
            "TCP_KEEPCNT",
            timeouts.get("keepcnt"),
            lambda x: None if x == "" else x,
        )
        _set(res, "TCP_KEEPALIVE", timeouts.get("keepalive"))
        _set(res, "MAX_PROBE_WAITTIME", timeouts.get("max_probe_wait"), _opt_td)

    if isinstance(limits := cfg.get("limits"), dict):
        _set(res, "MAX_QUEUE_SIZE", limits.get("max_queue_size"))

    if isinstance(gc := cfg.get("gc"), dict):
        _set(res, "GC_INTERVAL", gc.get("interval"), _td)
        _set(res, "QUEUE_GC_INTERVAL", gc.get("queues_interval"), _td)

    if isinstance(auth := cfg.get("auth"), dict):
        _set(
            res,
            "AUTH_HANDLER",
            auth.get("handler"),
            lambda x: _load_handler(x, cfg, module_loading_allowed),
        )

    _check_config(res)
    return res


def _load_env_config(
    cfg: dict[str, Any], module_loading_allowed: bool = False
) -> dict[str, Any]:
    res = {}

    for f in dataclasses.fields(Config):
        val = os.environ.get(f.name)
        if val is not None:
            if f.type == Optional[timedelta]:
                _set(res, f.name, val, _opt_td)
            elif f.type == timedelta:
                _set(res, f.name, val, _td)
            elif f.type == Optional[int]:
                res[f.name] = int(val) if val != "" else None
            elif f.type == AuthHandler:
                _set(
                    res,
                    f.name,
                    val,
                    lambda x: _load_handler(
                        x, cfg, allow_plugins=module_loading_allowed
                    ),
                )
            else:
                res[f.name] = f.type(val)

    _check_config(res)
    return res


def _check_config(cfg: dict[str, Any]):
    for f in dataclasses.fields(Config):
        val = cfg.get(f.name)
        if val is not None and not isinstance(val, f.type):
            LOGGER.error(
                f"Invalid configuration value for {f.name}: '{val}' expected {f.type}"
            )
            raise ConfigError


_CONFIG: Config | None = None


def init_config(path: str | Path, allow_third_party_modules: bool = False) -> Config:
    global _CONFIG

    if _CONFIG is not None:
        raise ConfigError

    if isinstance(path, str):
        path = Path(path)

    with open(path, "rb") as f:
        cfg = tomllib.load(f)

    conf = _load_toml_config(cfg, allow_third_party_modules) if path else None

    if conf is None:
        conf = {}

    conf.update(_load_env_config(cfg, allow_third_party_modules))

    try:
        _CONFIG = Config(**conf)
    except TypeError as e:
        raise ConfigError from e

    return _CONFIG


def get_config() -> Config:
    global _CONFIG

    if _CONFIG is None:
        LOGGER.info(
            "Configuration was accessed before being explicitly initialized. Initializing..."
        )
        if "MOAT-SIMTUNNEL-CONFIG" not in os.environ:
            raise ConfigError(
                "Can't find config file because 'MOAT-SIMTUNNEL-CONFIG' env var is not set."
            )
        return init_config(
            os.environ["MOAT-SIMTUNNEL-CONFIG"],
            "ALLOW_THIRD_PARTY_MODULES" in os.environ,
        )

    return _CONFIG