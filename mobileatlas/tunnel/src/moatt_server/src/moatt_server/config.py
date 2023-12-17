import tomllib
from typing import Any, Optional


def _load_toml_config():
    try:
        with open("config.toml", "rb") as f:
            return tomllib.load(f)
    except OSError:
        return {}


_config = _load_toml_config()


def _get_optional(name) -> Optional[Any]:
    v = _config.get(name)

    if v == "":
        return None
    else:
        return v


# TODO: find sensible defaults

# Time (in seconds) that the Server waits for an auth message before terminating the connection
AUTHMSG_TIMEOUT: int = int(_get_optional("authmsg_timeout") or 10)
PROVIDER_RESPONSE_TIMEOUT: int = int(_get_optional("provider_response_timeout") or 10)
PROBE_REQUEST_TIMEOUT: int = int(_get_optional("probe_request_timeout") or 10)
QUEUE_GC_INTERVAL: int = int(_get_optional("gc_interval") or 60)
GC_INTERVAL: int = int(_get_optional("gc_interval") or 60)
TCP_KEEPIDLE: int = int(_get_optional("tcp_keepidle") or 10)
TCP_KEEPINTVL: int = int(_get_optional("tcp_keepintvl") or 10)
TCP_KEEPCNT: int = int(_get_optional("tcp_keepcnt") or 10)
