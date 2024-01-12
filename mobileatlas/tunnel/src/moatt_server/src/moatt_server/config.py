import dataclasses
import functools
import logging
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)


# TODO: find sensible defaults
@dataclass(kw_only=True, frozen=True)
class Config:
    AUTHMSG_TIMEOUT: int = 10
    PROVIDER_RESPONSE_TIMEOUT: int = 10
    PROBE_REQUEST_TIMEOUT: int = 10
    TCP_KEEPIDLE: int = 10
    TCP_KEEPINTVL: int = 10
    TCP_KEEPCNT: int = 10
    MAX_QUEUE_SIZE: int = 10

    GC_INTERVAL: int = 60
    QUEUE_GC_INTERVAL: int = 60

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    def db_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


class ConfigError(Exception):
    """TODO"""


def _load_toml_config(path: Path) -> Optional[dict[str, Any]]:
    def _set(d: dict[str, Any], name: str, value: Optional[Any]):
        if value is not None:
            d[name] = value

    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except FileNotFoundError:
        LOGGER.info(f"Config file '{path.absolute()}' does not exist.")
        return None

    res = {}

    if isinstance(db := cfg.get("db"), dict):
        _set(res, "DB_HOST", db.get("host"))
        _set(res, "DB_PORT", db.get("port"))
        _set(res, "DB_USER", db.get("user"))
        _set(res, "DB_NAME", db.get("name"))
        _set(res, "DB_PASSWORD", db.get("password"))

    if isinstance(db := cfg.get("timeouts"), dict):
        _set(res, "AUTHMSG_TIMEOUT", db.get("authmsg"))
        _set(res, "PROVIDER_RESPONSE_TIMEOUT", db.get("provider_response"))
        _set(res, "PROBE_REQUEST_TIMEOUT", db.get("probe_request"))
        _set(res, "TCP_KEEPIDLE", db.get("keepidle"))
        _set(res, "TCP_KEEPINTVL", db.get("keepintvl"))
        _set(res, "TCP_KEEPCNT", db.get("keepcnt"))

    if isinstance(db := cfg.get("limits"), dict):
        _set(res, "MAX_QUEUE_SIZE", db.get("max_queue_size"))

    if isinstance(db := cfg.get("gc"), dict):
        _set(res, "GC_INTERVAL", db.get("interval"))
        _set(res, "QUEUE_GC_INTERVAL", db.get("queues_interval"))

    _check_config(res)
    return res


def _load_env_config() -> dict[str, Any]:
    res = {}

    for f in dataclasses.fields(Config):
        val = os.environ.get(f.name)
        if val is not None:
            res[f.name] = f.type(val)

    return res


def _check_config(cfg: dict[str, Any]):
    for f in dataclasses.fields(Config):
        val = cfg.get(f.name)
        if val is not None and not isinstance(val, f.type):
            LOGGER.error(
                f"Invalid configuration value for {f.name}: '{val}' expected {f.type}"
            )
            raise ConfigError


@functools.cache
def get_config() -> Config:
    conf = _load_toml_config(Path("config.toml"))

    if conf is None:
        conf = {}

    conf.update(_load_env_config())

    try:
        return Config(**conf)
    except TypeError as e:
        raise ConfigError from e
