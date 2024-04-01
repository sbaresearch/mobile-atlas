import logging
from dataclasses import dataclass
from uuid import UUID

from moatt_types.connect import ApduPacket, Token
from sqlalchemy.ext.asyncio import AsyncSession

from . import models as dbm
from .config import get_config

LOGGER = logging.getLogger(__name__)


@dataclass
class SimId:
    id: int
    iccid: str | None = None
    imsi: str | None = None


async def mark_provider_available(session: AsyncSession, provider_id: UUID) -> None:
    prov = await session.get(dbm.Provider, provider_id)

    assert prov is not None

    prov.available += 1


async def mark_provider_unavailable(session: AsyncSession, provider_id: UUID) -> None:
    prov = await session.get(dbm.Provider, provider_id)

    assert prov is not None

    prov.available -= 1


async def sim_used(session: AsyncSession, provider_id: UUID, sim_id: int) -> None:
    sim = await session.get(dbm.Sim, {"id": sim_id, "provider_id": provider_id})

    assert sim is not None, "Handler uses nonexistant SIM"

    sim.in_use = True


async def sim_unused(session: AsyncSession, provider_id: UUID, sim_id: int) -> None:
    sim = await session.get(dbm.Sim, {"id": sim_id, "provider_id": provider_id})

    if sim is None:
        return

    sim.in_use = False


async def get_sim_ids(
    session: AsyncSession, session_token: Token
) -> list[tuple[int, str | None, str | None]]:
    LOGGER.debug("Retrieving registered SIM cards.")

    authh = get_config().AUTH_HANDLER

    provider_id = await authh.identity(session_token)

    if provider_id is None:
        return []

    provider = await session.get(dbm.Provider, provider_id)

    if provider is None:
        return []

    sims: list[dbm.Sim] = await provider.awaitable_attrs.sims

    return list(map(lambda s: (s.id, s.iccid, s.imsi), sims))


async def log_apdu(
    session: AsyncSession,
    provider_id: UUID,
    probe_id: UUID,
    sim_id: SimId,
    apdu: ApduPacket,
    sender: dbm.Sender,
) -> dbm.ApduLog:
    apdu_log = dbm.ApduLog(
        provider_id=provider_id,
        probe_id=probe_id,
        sim_id=sim_id.id,
        sim_iccid=sim_id.iccid,
        sim_imsi=sim_id.imsi,
        command=apdu.op,
        payload=apdu.payload,
        sender=sender,
    )
    session.add(apdu_log)
    return apdu_log
