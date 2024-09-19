import asyncio
import base64
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from systemd.daemon import notify

from . import config
from .models import Peer, UrlSafeBase64

LOGGER = logging.getLogger(__name__)
WG_CONFIG_LOCK = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    notify("READY=1\n")
    yield
    notify("STOPPING=1\n")


app = FastAPI(lifespan=lifespan, **config.Settings.get().fastapi_doc_settings())

Settings = Annotated[config.Settings, Depends(config.Settings.get)]


@app.get("/status")
async def current_config(settings: Settings) -> str:
    """Returns status information for wireguard interface wg0.

    Raises
    ------
    CalledProcessError
        If wg command returns non-zero exit status
    """

    stdout = await sudo(
        "wg",
        "show",
        settings.interface,
    )

    return stdout.decode(errors="replace")


@app.put("/peers")
async def add_peer(peer: Peer, settings: Settings) -> None:
    """Adds a wireguard peer to the wg interface and saves the updated configuration file."""

    await sudo(
        "wg",
        "set",
        settings.interface,
        "peer",
        base64.b64encode(peer.pub_key).decode(),
        "allowed-ips",
        ",".join(map(lambda n: n.compressed, peer.allowed_ips)),  # type: ignore
    )

    LOGGER.info("Added/Changed wireguard peer: %s", peer.model_dump_json())

    await save_wg_config(settings)


@app.delete("/peers/{pub_key}")
async def delete_peer(pub_key: UrlSafeBase64, settings: Settings) -> None:
    """Deletes a wireguard peer from the wg interface and saves the updated configuration file."""

    await sudo(
        "wg",
        "set",
        settings.interface,
        "peer",
        pub_key,
        "remove",
    )

    LOGGER.info("Sucessfully removed wireguard peer: %s", pub_key)

    await save_wg_config(settings)


async def sudo(*args: str) -> bytes:
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/sudo",
        "-n",
        *args,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
        env={
            "WG_COLOR_MODE": "never",
            "WG_HIDE_KEYS": "always",
        }
    )

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 10)
    except TimeoutError:
        LOGGER.warning("The following process timed out after 10s: %s", " ".join(args))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    assert process.returncode is not None

    if process.returncode != 0:
        LOGGER.warning(
            "Program returned nonzero exit status: %s\n\n%s",
            " ".join(args),
            stderr.decode(errors="replace"),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return stdout


async def save_wg_config(settings: config.Settings):
    try:
        async with WG_CONFIG_LOCK:
            await sudo(
                "wg-quick",
                "save",
                settings.wg_config,
            )
    except Exception:
        LOGGER.exception(
            "Failed to save interface configuration to '%s'.", settings.wg_config
        )
        return

    LOGGER.info("Saved updated configuration file to: %s", settings.wg_config)
