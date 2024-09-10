import asyncio
import base64
import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import IPvAnyNetwork
from systemd.daemon import notify

from . import config
from .models import Peer

LOGGER = logging.getLogger(__name__)
WG_CONFIG_LOCK = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    notify("START=1", unset_environment=True)
    yield


app = FastAPI(lifespan=lifespan)

Settings = Annotated[config.Settings, Depends(config.Settings.get)]


@app.get("/status")
async def current_config(settings: Settings) -> str:
    """Returns status information for wireguard interface wg0.

    Raises
    ------
    CalledProcessError
        If wg command returns non-zero exit status
    """
    process = await asyncio.create_subprocess_exec(
        "/usr/bin/sudo",
        "-n",
        "wg",
        "show",
        settings.interface,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stdin=asyncio.subprocess.DEVNULL,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 10)
    except TimeoutError:
        LOGGER.warning(
            "wg process timed out after 10s while trying to get the interface status."
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if process.returncode != 0:
        LOGGER.warning(
            "Failed to print current wireguard interface configuration:\n%s",
            stderr.decode(errors="replace"),
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return stdout.decode(errors="replace")


@app.put("/peers")
async def add_peer(peer: Peer, settings: Settings) -> None:
    """Add a [Peer] section to the wg config."""

    process = await asyncio.create_subprocess_exec(
        "/usr/bin/sudo",
        "-n",
        "wg",
        "set",
        settings.interface,
        "peer",
        base64.b64encode(peer.pub_key),
        "allowed-ips",
        ",".join(map(lambda n: n.compressed, peer.allowed_ips)),  # type: ignore
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stdin=asyncio.subprocess.DEVNULL,
    )

    try:
        _, stderr = await asyncio.wait_for(process.communicate(), 10)
    except TimeoutError:
        LOGGER.warning("wg process timed out after 10s while trying to add a peer.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if process.returncode != 0:
        LOGGER.warning(
            "Failed to set peer configuration:\n%s", stderr.decode(errors="replace")
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    LOGGER.info("Added/Changed wireguard peer: %s", peer.model_dump_json())

    await save_wg_config(settings)


async def save_wg_config(settings: config.Settings):
    async with WG_CONFIG_LOCK:
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/sudo",
            "-n",
            "wg-quick",
            "save",
            settings.wg_config,
            stderr=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.DEVNULL,
            stdin=asyncio.subprocess.DEVNULL,
        )

        try:
            _, stderr = await asyncio.wait_for(process.communicate(), 10)
        except TimeoutError:
            LOGGER.warning(
                "wg-quick timed out after 10s while trying to save the configuration."
            )
            return

        if process.returncode != 0:
            LOGGER.warning(
                "Failed to save wireguard configuration.\n%s",
                stderr.decode(errors="replace"),
            )
