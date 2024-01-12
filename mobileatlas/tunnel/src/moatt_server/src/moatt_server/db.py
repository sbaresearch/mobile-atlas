import logging

from moatt_types.connect import Iccid, SessionToken
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from . import models as dbm
from .auth import get_session_token, get_sim

LOGGER = logging.getLogger(__name__)


async def provider_available(session: AsyncSession, provider_id: int) -> None:
    res = await session.scalar(
        update(dbm.Provider)
        .where(dbm.Provider.id == provider_id)
        .values(available=dbm.Provider.available + 1)
    )
    assert res == 1


async def provider_unavailable(session: AsyncSession, provider_id: int) -> None:
    res = await session.scalar(
        update(dbm.Provider)
        .where(dbm.Provider.id == provider_id)
        .values(available=dbm.Provider.available - 1)
    )
    assert res == 1


async def sim_used(
    session: AsyncSession, session_token: dbm.SessionToken, identifier: Iccid
) -> None:
    sim = await get_sim(session, session_token, identifier)

    assert sim is not None, "Handler uses nonexistant SIM"

    sim.in_use = True


async def sim_unused(
    session: AsyncSession, session_token: dbm.SessionToken, identifier: Iccid
) -> None:
    sim = await get_sim(session, session_token, identifier)

    if sim is None:
        return

    sim.in_use = False


async def get_imsi(session: AsyncSession, sim: dbm.Sim) -> dbm.Imsi | None:
    return await session.scalar(
        select(dbm.Imsi)
        .where(dbm.Imsi.sim_iccid == sim.iccid)
        .order_by(dbm.Imsi.registered.desc())
        .limit(1)
    )


async def get_sim_ids(
    session: AsyncSession, session_token: SessionToken
) -> list[tuple[str, str | None]]:
    LOGGER.debug("Retrieving registered SIM cards.")

    stoken = await get_session_token(session, session_token)

    if stoken.provider is None:
        return []

    sims = await stoken.provider.awaitable_attrs.sims

    sim_ids: list[tuple[str, str | None]] = []
    for sim in sims:
        imsi = await get_imsi(session, sim)

        sim_ids.append((sim.iccid, imsi.imsi if imsi else None))

    return sim_ids
