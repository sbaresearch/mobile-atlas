import datetime
import logging
from typing import Optional
from uuid import UUID

from moatt_types.connect import AuthStatus, Iccid, Imsi, SessionToken, SimId, SimIndex
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models as dbm
from .auth_handler import AuthResult, SimIdents, auth_handler
from .config import get_config

LOGGER = logging.getLogger(__name__)


class TokenError(Exception):
    def __init__(self, etype: AuthResult) -> None:
        self.etype = etype

    def to_auth_status(self) -> AuthStatus:
        match self.etype:
            case AuthResult.Success:
                return AuthStatus.Success
            case AuthResult.InvalidToken | AuthResult.ExpiredToken | AuthResult.Forbidden:
                return AuthStatus.Unauthorized
            case AuthResult.NotRegistered:
                return AuthStatus.NotRegistered
            case _:
                raise NotImplementedError


class Sim:
    def __init__(self, iccid: Iccid, imsi: Imsi | None):
        self.iccid = iccid
        self.imsi = imsi


def now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


async def register_provider(
    session: AsyncSession,
    session_token: SessionToken,
    sims: dict[int, tuple[Iccid | None, Imsi | None]],
) -> bool:
    LOGGER.debug(f"Registering SIMs. {sims}")

    authh = auth_handler()

    if (
        auth_res := await authh.allowed_provider_registration(session_token)
    ) != AuthResult.Success:
        raise TokenError(auth_res)

    iccids, imsis = list(zip(*sims.values()))

    if (
        auth_res := await authh.allowed_sim_registration(session_token, sims)
    ) != AuthResult.Success:
        raise TokenError(auth_res)

    provider_id = authh.identity(session_token)

    if provider_id is None:
        raise TokenError(AuthResult.InvalidToken)

    provider = await session.get(dbm.Provider, provider_id)

    modified = False
    time = now()

    if provider is None:
        modified = True
        provider = dbm.Provider(id=provider_id, last_active=time)
        session.add(provider)

    ids = list(sims.keys())

    removed_sims = list(
        await session.scalars(
            select(dbm.Sim).where(
                (dbm.Sim.provider_id == provider_id) & (dbm.Sim.id.not_in(ids))
            )
        )
    )

    if len(removed_sims) > 0:
        modified = True

    for sim in removed_sims:
        await session.delete(sim)

    if len(sims) == 0:
        return modified

    existing_sims = list(
        await session.scalars(
            select(dbm.Sim).where(dbm.Sim.iccid.in_(iccids) | dbm.Sim.imsi.in_(imsis))
        )
    )
    new_ids = set(ids)

    for sim in existing_sims:
        if (
            sim.provider.id == provider_id
        ):  # TODO: test changing already registered sims -> defer constraint check??
            new_sim = sims[sim.id]
            iccid = new_sim[0].iccid if new_sim[0] is not None else None
            imsi = new_sim[1].imsi if new_sim[1] is not None else None

            if sim.iccid != iccid or sim.imsi != imsi:
                modified = True
                await session.delete(sim)
            else:
                new_ids.remove(sim.id)

            continue

        if sim.provider.is_expired(get_config().PROVIDER_EXPIRATION):
            await remove_provider(session, sim.provider)
        elif sim.provider.allow_reregistration is False:
            raise AuthError

        await session.delete(sim)

    if len(new_ids) > 0:
        modified = True

    for id in new_ids:
        sim = dbm.Sim(
            id=id,
            iccid=sims[id][0],
            imsi=sims[id][1],
            in_use=False,
            provider=provider,
        )
        session.add(sim)

    return modified


async def deregister_provider(
    session: AsyncSession, session_token: SessionToken
) -> None:
    authh = auth_handler()

    prov_id = await authh.identity(session_token)

    if prov_id is None:
        return

    provider = await session.get(dbm.Provider, prov_id)

    if provider is None:
        return

    await remove_provider(session, provider)


async def remove_provider(session: AsyncSession, provider: dbm.Provider) -> None:
    await session.delete(provider)


class AuthError(Exception):
    """Authorisation failure."""


async def identity(token: SessionToken) -> UUID | None:
    authh = auth_handler()

    return await authh.identity(token)


async def register_probe(token: SessionToken) -> None:
    authh = auth_handler()

    if (res := await authh.allowed_probe_registration(token)) != AuthResult.Success:
        raise TokenError(res)


async def provider_registered(session: AsyncSession, token: SessionToken) -> None:
    authh = auth_handler()

    if (res := await authh.allowed_provider_registration(token)) != AuthResult.Success:
        raise TokenError(res)

    identity = await authh.identity(token)

    if identity is None:
        raise TokenError(AuthResult.InvalidToken)

    provider = await session.get(dbm.Provider, identity)

    if provider is None:
        raise TokenError(AuthResult.NotRegistered)


async def get_sim(
    session: AsyncSession,
    token: SessionToken,
    identifier: SimId | Iccid | Imsi | SimIndex,
) -> Optional[dbm.Sim]:
    LOGGER.debug(f"Retrieving SIM card. {identifier=}")

    authh = auth_handler()

    match identifier:
        case SimId(id=id):
            prov_id = await authh.identity(token)

            if prov_id is None:
                return None

            sim = await session.scalar(
                select(dbm.Sim).where(
                    (dbm.Sim.provider_id == prov_id) & (dbm.Sim.id == id)
                )
            )
        case Iccid(iccid=iccid):
            sim = await session.scalar(select(dbm.Sim).where(dbm.Sim.iccid == iccid))
        case Imsi(imsi=imsi):
            sim = await session.scalar(select(dbm.Sim).where(dbm.Sim.imsi == imsi))
        case SimIndex(index=index):
            sim = await session.scalar(
                select(dbm.Sim).order_by(dbm.Sim.id.asc()).limit(1).offset(index)
            )
        case _:
            raise NotImplementedError

    if sim is None:
        raise AuthError  # raise an AuthError to make it harder to check whether arbitrary ids are registered

    if not authh.allowed_sim_request(
        token,
        (await sim.awaitable_attrs.provider).id,
        SimIdents(id=sim.id, iccid=sim.iccid, imsi=sim.imsi),
    ):
        raise AuthError

    return sim
