import asyncio
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import exc as sqlexc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import config
from . import pydantic_models as pyd
from .auth import bearer_token_probe
from .config import get_config
from .db import get_db
from .models import (
    MamToken,
    Probe,
    ProbeServiceStartupLog,
    ProbeStatus,
    ProbeStatusType,
    ProbeSystemInformation,
)

"""
Endpoints called from the Measurement Probe are listed in this file
"""

router = APIRouter(prefix="/probe", tags=["probe"])


@router.post("/startup")
async def startup_log(
    token: Annotated[MamToken, Depends(bearer_token_probe)],
    session: Annotated[AsyncSession, Depends(get_db)],
    mac: pyd.Mac,
):
    await session.begin()
    session.add(token)
    await session.refresh(token)

    if token.mac != mac.mac:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST)

    # Create a log entry
    prl = ProbeServiceStartupLog(
        probe_id=(await token.awaitable_attrs.probe).id,
        mac=mac.mac,
        timestamp=datetime.now(tz=timezone.utc),
    )
    session.add(prl)
    await session.commit()


@router.post("/poll")
async def probe_poll(
    token: Annotated[MamToken, Depends(bearer_token_probe)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> pyd.Command | None:
    """
    The long poll endpoint for the probe
    """

    await session.begin()
    session.add(token)
    await session.refresh(token)

    now = datetime.now(tz=timezone.utc)
    probe = await token.awaitable_attrs.probe
    probe.last_poll = now

    # Include a status update
    #
    # (1) No last status - create a new status
    # (2) Got last status
    #     (2a) Expired - Finish old status - create new status
    #     (2b) Active - Prolong active status
    ps = await session.scalar(
        select(ProbeStatus).where(
            (ProbeStatus.probe_id == probe.id) & (ProbeStatus.active == True)
        )
    )
    interval = get_config().LONG_POLLING_INTERVAL

    if ps is not None:
        # Case (2b)
        if ps.status == ProbeStatusType.online and ps.end + interval * 2 > now:
            ps.end = now
        # Case (2a)
        else:
            ps.active = False
            ps.end = now

            # Set to None so that a new Status is created
            ps = None

    # Case (1)
    if not ps:
        ps = ProbeStatus(
            probe_id=probe.id,
            active=True,
            status=ProbeStatusType.online,
            begin=now,
            end=now + timedelta(milliseconds=1),
        )
        session.add(ps)

    # We save the id before commit is called
    # because commit expires the probe object
    probe_id = probe.id
    await session.commit()

    # Connect to redis queue and wait for command
    pubsub = config.get_config().redis_client().pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(f"probe:{probe_id}")

    try:
        msg = await asyncio.wait_for(
            anext(pubsub.listen()), get_config().LONG_POLLING_INTERVAL.total_seconds()
        )
        return pyd.Command(command=msg["data"].decode())
    except TimeoutError:
        pass


@router.post("/system_information")
async def probe_system_information(
    token: Annotated[MamToken, Depends(bearer_token_probe)],
    session: Annotated[AsyncSession, Depends(get_db)],
    json: pyd.Json,
) -> None:
    """
    Endpoint for Uploading ProbeSystemInformation
    """

    await session.begin()
    session.add(token)
    await session.refresh(token)

    probe = await token.awaitable_attrs.probe

    psi = ProbeSystemInformation(
        probe_id=probe.id,
        timestamp=datetime.now(tz=timezone.utc),
        information=json.root,
    )
    session.add(psi)
    await session.commit()


async def after_token_activation(
    session: AsyncSession, token: MamToken, name: str
) -> None:
    session.add(
        Probe(
            name=name,
            token=token,
        )
    )


async def before_token_deletion(session: AsyncSession, token: MamToken) -> None:
    pass


async def handle_activation_error(
    session: AsyncSession, exc: Exception, token: MamToken, name: str
) -> None:
    if isinstance(exc, sqlexc.IntegrityError):
        duplicate_name = await session.scalar(
            select(Probe).where((Probe.name == name) & (Probe.token_id != token.id))
        )

        if duplicate_name is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Probe name is not unique.",
            )
