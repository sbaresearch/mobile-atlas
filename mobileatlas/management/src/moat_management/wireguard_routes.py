import ipaddress
import logging
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from ipaddress import IPv4Address, IPv6Address
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import exc as sqlexc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import pydantic_models as pyd
from .auth import bearer_token_wg, get_basic_auth_admin
from .config import get_config
from .db import get_db
from .models import MamToken, WireguardConfig, WireguardConfigLogs
from .resources import get_templates

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/wireguard", tags=["wireguard"])


async def get_wg_daemon_client() -> AsyncGenerator[httpx.AsyncClient | None, None]:
    url = get_config().WIREGUARD_DAEMON

    if url is None:
        yield None
        return

    if url.startswith("unix:"):
        transport = httpx.AsyncHTTPTransport(uds=url.removeprefix("unix:"))

        async with httpx.AsyncClient(
            transport=transport, base_url="http://wg-daemon"
        ) as c:
            yield c
    else:
        async with httpx.AsyncClient(base_url=url) as c:
            yield c


async def get_client_ip(
    req: Request,
    x_real_ip: Annotated[str | None, Header()] = None,
) -> IPv4Address | IPv6Address:
    if get_config().SERVER_BEHIND_PROXY:
        ip = x_real_ip
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
    basic_auth: Annotated[str, Depends(get_basic_auth_admin)],
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    wgd_client: Annotated[httpx.AsyncClient, Depends(get_wg_daemon_client)],
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
        "status": await get_current_wireguard_status(wgd_client),
    }
    return get_templates().TemplateResponse(
        request=request, name="wireguard.html", context=ctx
    )


@router.post("/register")
async def wireguard_register(
    token: Annotated[MamToken, Depends(bearer_token_wg)],
    session: Annotated[AsyncSession, Depends(get_db)],
    client_ip: Annotated[IPv4Address | IPv6Address, Depends(get_client_ip)],
    wgd_client: Annotated[httpx.AsyncClient, Depends(get_wg_daemon_client)],
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
            await wireguard_put_peer(publickey, wg.ip, wgd_client)
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


async def wireguard_put_peer(
    publickey: str, ip: str, client: httpx.AsyncClient
) -> None:
    """
    Configure Wireguard locally

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg addconf wg0 /tmp/wireguard
    """
    r = await client.put("/peers", json={"pub_key": publickey, "allowed_ips": [ip]})

    if not r.is_success:
        LOGGER.warning(
            "Wireguard service returned non success status (%d):\n%s",
            r.status_code,
            r.content,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def get_current_wireguard_status(client: httpx.AsyncClient) -> str | None:
    """
    Get the current wireguard config

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg showconf wg0
    """
    r = await client.get("/status")

    if not r.is_success:
        LOGGER.warning(
            "Failed to get current wireguard interface status from wg daemon (%d).\n%s",
            r.status_code,
            r.content,
        )
        return None

    json = r.json()

    if not isinstance(json, str):
        LOGGER.warning("wg-daemon did not return a JSON string.")
        return None

    return json


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
