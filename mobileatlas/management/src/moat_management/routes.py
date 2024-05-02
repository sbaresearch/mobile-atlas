import asyncio
import enum
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import httpx
import pycountry
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import pydantic_models as pyd
from .auth import get_basic_auth
from .config import get_config
from .db import get_db
from .models import MamToken, Probe, ProbeStatus, ProbeStatusType
from .resources import get_templates

LOGGER = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_basic_auth)])

Session = Annotated[AsyncSession, Depends(get_db)]


@router.get("/")
def index(
    request: Request,
):
    """
    Show no content ... only base
    """
    return get_templates().TemplateResponse(request=request, name="index.html")


@router.get("/probes")
async def probes(
    request: Request,
    session: Session,
):
    """
    Show all probes
    """
    await session.begin()
    load_attrs = [Probe.status, Probe.system_info, Probe.startup_log]
    all_probes = (
        await session.scalars(
            select(Probe).options(
                selectinload(Probe.token).selectinload(MamToken.logs),
                *map(selectinload, load_attrs),
            )
        )
    ).all()

    ctx = {
        "probes": all_probes,
        "format_country": format_country,
    }

    return get_templates().TemplateResponse(
        request=request, name="probes.html", context=ctx
    )


async def _check_probe_statuses(session: AsyncSession):
    """
    Check Status of all probes, and turn to offline or prolongen offline
    This is to be called by a cronjob - See status_check_cron.py
    :return: JSON of newly offline Probes
    """
    LOGGER.info("Updating probe statuses.")
    online_statuses = await session.scalars(
        select(ProbeStatus).where(ProbeStatus.active)
    )
    # When end datetime is due + interval, close active one and create new offline
    interval = get_config().LONG_POLLING_INTERVAL
    now = datetime.now(tz=timezone.utc)

    offline_for = timedelta(minutes=30)
    notification = []

    for ps in online_statuses:
        if ps.status == ProbeStatusType.online and ps.end + interval < now:
            ps.active = False
            ps_offline = ProbeStatus(
                probe_id=ps.probe_id,
                active=True,
                status=ProbeStatusType.offline,
                begin=ps.end,
                end=ps.end + timedelta(milliseconds=1),
            )
            session.add(ps_offline)
        elif ps.status == ProbeStatusType.offline:
            offline_duration_before = ps.duration()
            ps.end = now
            offline_duration_after = ps.duration()
            if offline_duration_before < offline_for <= offline_duration_after:
                await ps.awaitable_attrs.probe
                notification.append(ps.probe.to_dict())

        session.add(ps)

    webhook_url = get_config().NOTIFICATION_WEBHOOK

    if webhook_url is None:
        return

    try:
        for n in notification:
            text = f"Probe {n['name']+' - '+n['mac'] if 'name' in n and n['name'] else n['mac']} is offline for 30 minutes"
            httpx.post(webhook_url, json={"text": text})
    except Exception as e:
        LOGGER.warning(f"Failed to push notifications to webhook. ({e})")


async def check_probe_statuses(session: AsyncSession):
    while True:
        try:
            await asyncio.sleep(60)
            async with session.begin():
                await _check_probe_statuses(session)
        except Exception:
            LOGGER.exception(
                "Exception occurred while trying to update probe statuses."
            )


@router.get("/probe/{probe_id}")
async def probe_details(probe_id: UUID, request: Request, session: Session):
    """
    Show details of probe
    """
    await session.begin()
    p = await session.get(Probe, probe_id)

    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await p.awaitable_attrs.token
    await p.awaitable_attrs.startup_log
    await p.awaitable_attrs.status
    await p.awaitable_attrs.system_info
    await p.token.awaitable_attrs.logs

    _, percentages = p.get_status_statistics()

    ctx = {
        "p": p,
        "percentages": percentages,
        "format_country": format_country,
    }

    return get_templates().TemplateResponse(
        request=request, name="probe.html", context=ctx
    )


@router.get("/probe/{probe_id}/systeminformations")
async def probe_systeminformations(
    probe_id: UUID,
    request: Request,
    session: Session,
):
    """
    Show all service systeminformations for one probe
    """
    await session.begin()
    p = await session.get(Probe, probe_id)

    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await p.awaitable_attrs.token
    await p.awaitable_attrs.system_info

    return get_templates().TemplateResponse(
        request=request, name="probe_systeminformations.html", context={"p": p}
    )


@router.get("/probe/{probe_id}/startups")
async def probe_startups(
    probe_id: UUID,
    request: Request,
    session: Session,
):
    """
    Show all service startups for one probe
    """
    await session.begin()
    p = await session.get(Probe, probe_id)

    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await p.awaitable_attrs.token
    await p.awaitable_attrs.startup_log

    return get_templates().TemplateResponse(
        request=request, name="probe_startups.html", context={"p": p}
    )


@router.get("/probe/{probe_id}/status")
async def probe_status(
    probe_id: UUID,
    request: Request,
    session: Session,
):
    """
    Show all status for one probe
    """
    await session.begin()
    p = await session.get(Probe, probe_id)

    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await p.awaitable_attrs.token
    await p.awaitable_attrs.status
    await p.token.awaitable_attrs.logs
    durations, percentages = p.get_status_statistics()

    ctx = {
        "p": p,
        "durations": durations,
        "percentages": percentages,
    }
    return get_templates().TemplateResponse(
        request=request, name="probe_status.html", context=ctx
    )


@router.post("/probe/{probe_id}/change_name/{name}")
async def change_probe_name(
    probe_id: UUID,
    name: str,
    session: Session,
):
    await session.begin()

    p = await session.get(Probe, probe_id)

    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    p.name = name
    await session.commit()


@router.post("/probe/{probe_id}/change_country")
async def change_country(
    probe_id: UUID,
    args: pyd.ChangeCountry,
    session: Session,
):
    await session.begin()

    p = await session.get(Probe, probe_id)

    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    try:
        country = pycountry.countries.search_fuzzy(args.country)[0]
    except:
        return "found no matching country", 404

    p.country = country.alpha_2  # type: ignore
    await session.commit()


@enum.unique
class ProbeCommand(str, enum.Enum):
    Exit = "exit"
    SystemInfo = "system_information"
    GitPull = "git_pull"


@router.post("/probe/{probe_id}/execute/{command}")
async def execute_probe(probe_id: UUID, command: ProbeCommand, session: Session):
    await session.begin()

    p = await session.get(Probe, probe_id)

    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    await get_config().redis_client().publish(f"probe:{probe_id}", command.value)


def format_country(country):
    try:
        country = pycountry.countries.get(alpha_2=country)
    except:
        return "n/a"

    if country is None:
        return "n/a"

    return f"{country.name} {country.flag}"
