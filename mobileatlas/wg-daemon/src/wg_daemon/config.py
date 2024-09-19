import functools
import os
from typing import Any, Self

from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource

ENV_CONF_PATH = "WG_DAEMON_CONFIG_FILE"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="wg_daemon_", toml_file="wg-daemon.toml"
    )

    interface: str = "wg0"
    wg_config: str = "/etc/wireguard/wg0.conf"
    documentation: bool = False

    def fastapi_doc_settings(self) -> dict[str, Any]:
        if self.documentation:
            return {}
        else:
            return {"docs_url": None, "redoc_url": None}

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        kwargs = {}
        if ENV_CONF_PATH in os.environ:
            kwargs["toml_file"] = os.environ[ENV_CONF_PATH]

        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls, **kwargs),
        )

    @classmethod
    @functools.cache
    def get(cls) -> Self:
        return cls()
