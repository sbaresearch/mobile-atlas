import asyncio
import base64
import ipaddress
import logging
import socket
import subprocess
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import exc as sqlexc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import pydantic_models as pyd
from .auth import bearer_token_wg, get_basic_auth
from .config import get_config
from .db import get_db
from .models import MamToken, WireguardConfig, WireguardConfigLogs
from .resources import get_templates

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/wireguard", tags=["wireguard"])


async def get_client_ip(
    req: Request,
    http_x_forwarded_for: Annotated[
        str | None, Header(convert_underscores=False)
    ] = None,
) -> IPv4Address | IPv6Address:
    if get_config().BEHIND_PROXY:
        ip = http_x_forwarded_for
    else:
        ip = req.client.host if req.client is not None else None

    if ip is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to determine client IP address.",
        )

    try:
        ip = ipaddress.ip_address(ip)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse client IP address.",
        ) from e

    return ip


@router.get("")
async def wireguard_index(
    basic_auth: Annotated[str, Depends(get_basic_auth)],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
):
    await session.begin()
    wgs = (
        await session.scalars(
            select(WireguardConfig).options(selectinload(WireguardConfig.token))
        )
    ).all()
    wgas = list(
        await session.scalars(
            select(WireguardConfigLogs)
            .order_by(WireguardConfigLogs.register_time.desc())
            .limit(10)
        )
    )
    wgas.reverse()
    token_reqs = (
        await session.scalars(select(MamToken).where(MamToken.token == None))
    ).all()
    ctx = {
        "wgs": wgs,
        "wgas": wgas,
        "token_reqs": token_reqs,
        "config": await get_current_wireguard_config(),
        "status": await get_current_wireguard_status(),
    }
    return get_templates().TemplateResponse(
        request=request, name="wireguard.html", context=ctx
    )


@router.post("/register")
async def wireguard_register(
    token: Annotated[MamToken, Depends(bearer_token_wg)],
    session: Annotated[AsyncSession, Depends(get_db)],
    client_ip: Annotated[IPv4Address | IPv6Address, Depends(get_client_ip)],
    reg: pyd.RegisterReq,
) -> pyd.WgConfig:
    """
    Register the public key of a Probe for Wireguard
    Expects arguments "mac" and "publickey"
    """
    async with session.begin():
        session.add(token)
        await session.refresh(token)
        log = await log_config_attempt(
            session, client_ip, token, reg.publickey, False, reg.mac
        )

    publickey = reg.publickey

    await session.begin()
    session.add(token)
    await session.refresh(token)
    await token.awaitable_attrs.config

    if token.config is None:
        # This should not happen: If wgtoken is active (wgtoken.token is not None)
        # then it should have a corresponding WireguardConfig
        await session.delete(token)
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token."
        )
    else:  # If there is a probe, update
        wg = token.config
        if not wg.allow_registration:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Registration not allowed.",
            )
        else:
            # Update Values
            wg.publickey = publickey
            await wireguard_configuration(publickey, wg.ip)
            wg.allow_registration = False
            wg.register_time = datetime.now(tz=timezone.utc)

            if token.mac is None:
                token.mac = reg.mac

            # Log the successful attempt
            session.add(log)
            log.successful = True
            session.add(wg)

            config = dict()
            config["ip"] = wg.ip
            config["endpoint"] = get_config().WIREGUARD_ENDPOINT
            config["endpoint_publickey"] = get_config().WIREGUARD_PUBLIC_KEY
            config["allowed_ips"] = get_config().WIREGUARD_ALLOWED_IPS
            config["dns"] = get_config().WIREGUARD_DNS

            await session.commit()

            return pyd.WgConfig(**config)


async def log_config_attempt(
    session: AsyncSession,
    ip: IPv4Address | IPv6Address | None,
    token: MamToken,
    publickey: str,
    successful: bool = False,
    mac: str | None = None,
) -> WireguardConfigLogs:
    log = WireguardConfigLogs(
        token=token.token_value(),
        mac=mac,
        publickey=publickey,
        register_time=datetime.now(tz=timezone.utc),
        ip=ip.exploded if ip is not None else None,
        successful=successful,
    )
    session.add(log)
    return log


async def wireguard_configuration(publickey: str, ip: str) -> None:
    """
    Configure Wireguard locally

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg addconf wg0 /tmp/wireguard
    """
    try:
        if not publickey.isascii() or len(base64.b64decode(publickey)) != 32:
            raise Exception
        # use inet_ntoa to get rid of abbreviated addresses
        # e.g. '127.1'
        ip = socket.inet_ntoa(socket.inet_aton(ip))
    except:
        raise Exception("invalid publickey")

    # Start with writing the config to a temprary file
    await asyncio.to_thread(_write_wg_conf, publickey, ip)

    subprocess.Popen(f"sudo wg addconf wg0 /tmp/wireguard", shell=True).wait()
    # TODO somehow log the changed configs to return to something different


def _write_wg_conf(publickey: str, ip: str) -> None:
    with open("/tmp/wireguard", "w") as tf:
        tf.write(f"[Peer]\n")
        tf.write(f"PublicKey = {publickey}\n")
        tf.write(f"AllowedIPs = {ip}/32\n\n")


async def get_current_wireguard_config() -> str | subprocess.CalledProcessError:
    """
    Get the current wireguard config

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg showconf wg0
    """
    try:
        return (
            await asyncio.to_thread(
                subprocess.check_output,
                f"sudo wg showconf wg0 | grep -v PrivateKey",
                shell=True,
            )
        ).decode()
    except subprocess.CalledProcessError as e:
        return e


async def get_current_wireguard_status() -> str | subprocess.CalledProcessError:
    """
    Get the current wireguard status

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg show wg0
    """
    try:
        return (
            await asyncio.to_thread(
                subprocess.check_output, f"sudo wg show wg0", shell=True
            )
        ).decode()
    except subprocess.CalledProcessError as e:
        return e


async def after_token_activation(
    session: AsyncSession, token: MamToken, ip: IPv4Address | IPv6Address
):
    if (config := await token.awaitable_attrs.config) is not None:
        config.ip = ip.exploded
        config.allow_registration = True
    else:
        wgc = WireguardConfig(
            token=token,
            ip=ip.exploded,
            allow_registration=True,
        )
        session.add(wgc)
    session.add(token)


async def handle_activation_error(
    session: AsyncSession,
    exc: Exception,
    token: MamToken,
    ip: IPv4Address | IPv6Address,
):
    if isinstance(exc, sqlexc.IntegrityError):
        duplicate_ip = await session.scalar(
            select(WireguardConfig).where(
                (WireguardConfig.ip == ip.exploded)
                & (WireguardConfig.token_id != token.id)
            )
        )
        if duplicate_ip is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="ip is not unique"
            )
