import datetime
import enum
import logging
import secrets
import typing
from typing import Optional

from moatt_types.connect import (
    ApduPacket,
    AuthStatus,
    Iccid,
    IdentifierType,
    Imsi,
    SessionToken,
    Token,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from . import models as dbm

LOGGER = logging.getLogger(__name__)


@enum.unique
class TokenErrorType(enum.Enum):
    Invalid = 0
    Expired = 1


class TokenError(Exception):
    def __init__(self, etype: TokenErrorType) -> None:
        self.etype = etype

    def to_auth_status(self) -> AuthStatus:
        if self.etype in [TokenErrorType.Invalid, AuthStatus.Unauthorized]:
            return AuthStatus.Unauthorized
        else:
            raise NotImplementedError


class Sim:
    def __init__(self, iccid: Iccid, imsi: Imsi):
        self.iccid = iccid
        self.imsi = imsi


def now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)


def generate_session_token() -> SessionToken:
    return SessionToken(secrets.token_bytes(25))


async def insert_new_session_token(
    session: AsyncSession, token_id, expires: Optional[datetime.timedelta] = None
) -> SessionToken:
    LOGGER.debug(f"Creating new session token. {expires=}")
    stoken = generate_session_token()
    time = now()
    session.add(
        dbm.SessionToken(
            value=stoken.as_base64(),
            created=time,
            last_access=time,
            token_id=token_id,
            expires=time + expires if expires is not None else None,
        )
    )
    return stoken


async def deregister_session(
    session: AsyncSession, session_token: SessionToken
) -> bool:
    LOGGER.debug("Deregistering session.")
    stoken = await session.get(
        dbm.SessionToken,
        session_token.as_base64(),
        options=[selectinload(dbm.SessionToken.provider)],
    )

    if stoken is None:
        return False

    if stoken.provider is not None:
        await session.delete(stoken.provider)

    await session.delete(stoken)

    return True


async def register_provider(
    session: AsyncSession, session_token: SessionToken, sims: dict[Iccid, Sim]
) -> bool:
    LOGGER.debug(f"Registering SIMs. {sims}")
    created = False
    stoken = await session.get(
        dbm.SessionToken,
        session_token.as_base64(),
        options=[selectinload(dbm.SessionToken.provider)],
    )

    if stoken is None:
        raise TokenError(TokenErrorType.Invalid)

    time = now()
    stoken.last_access = time

    if stoken.provider is None:
        created = True
        provider = dbm.Provider(session_token_id=stoken.value)
        session.add(provider)
    else:
        provider = stoken.provider

    iccids = list(map(lambda x: x.iccid, sims.keys()))

    removed_sims = await session.scalars(
        select(dbm.Sim)
        .where(dbm.Sim.provider_id == provider.id)
        .where(dbm.Sim.iccid.not_in(iccids))
    )

    for sim in removed_sims:
        sim.provider = None

    if len(sims) == 0:
        return created

    existing_sims = list(
        await session.scalars(select(dbm.Sim).where(dbm.Sim.iccid.in_(iccids)))
    )
    new_iccids = set(iccids).difference(set([sim.iccid for sim in existing_sims]))

    for sim in existing_sims:
        imsi = sims[Iccid(sim.iccid)].imsi.imsi

        if sim.provider is not None:
            if sim.provider.id == provider.id:
                continue

            if sim.provider.session_token.is_expired():
                await deregister_session(
                    session, sim.provider.session_token.to_con_type()
                )
            elif sim.provider.allow_reregistration is False:
                raise AuthError

        sim.provider = provider
        session.add(dbm.Imsi(imsi=imsi, registered=time, sim=sim))

    for iccid in new_iccids:
        sim = dbm.Sim(
            iccid=iccid,
            imsi=[dbm.Imsi(imsi=sims[Iccid(iccid)].imsi.imsi, registered=time)],
            available=True,
            provider=provider,
        )
        session.add(sim)

    return created


class AuthError(Exception):
    """Authorisation failure."""


async def valid_token(session: AsyncSession, token: Token) -> bool:
    result = await session.get(dbm.Token, token.as_base64())

    if result is None:
        return False

    return result.is_valid()


async def log_apdu(
    session: AsyncSession,
    sim_id: str,
    apdu: ApduPacket,
    sender: dbm.Sender,
) -> dbm.ApduLog:
    apdu_log = dbm.ApduLog(
        sim_id=sim_id,
        command=apdu.op,
        payload=apdu.payload,
        sender=sender,
    )
    session.add(apdu)
    return apdu_log


async def get_session_token(
    session: AsyncSession, session_token: SessionToken
) -> dbm.SessionToken:
    assert isinstance(session_token, SessionToken)

    stmt = (
        select(dbm.SessionToken)
        .where(dbm.SessionToken.value == session_token.as_base64())
        .options(selectinload(dbm.SessionToken.provider))
        .options(selectinload(dbm.SessionToken.token))
    )
    st = await session.scalar(stmt)

    if st is None:
        raise TokenError(TokenErrorType.Invalid)

    st.last_access = now()

    if st.is_valid():
        return st
    elif st.is_expired():
        raise TokenError(TokenErrorType.Expired)
    else:
        raise TokenError(TokenErrorType.Invalid)


async def get_sim(
    session: AsyncSession,
    session_token: dbm.SessionToken,
    identifier: Imsi | Iccid,
) -> Optional[dbm.Sim]:
    LOGGER.debug(f"Retrieving SIM card. {identifier=}")

    if not session_token.is_valid():
        raise AuthError

    time = now()
    session_token.last_access = time
    token = session_token.token
    token.last_access = time

    if identifier.identifier_type() == IdentifierType.Imsi:
        imsi = typing.cast(Imsi, identifier).imsi
        stmt = (
            select(dbm.Sim)
            .join(dbm.Sim.imsi)
            .where(dbm.Imsi.imsi == imsi)
            .order_by(dbm.Imsi.id.desc())
            .limit(1)
            .options(selectinload(dbm.Sim.provider))
        )
        sim = await session.scalar(stmt)

        if sim is None:
            return None

        session.add(token)
        await session.commit()

        return sim
    else:
        iccid = typing.cast(Iccid, identifier).iccid
        stmt = (
            select(dbm.Sim)
            .where(dbm.Sim.iccid == iccid)
            .options(selectinload(dbm.Sim.provider))
        )
        sim = await session.scalar(stmt)

        if sim is None:
            return None

        session.add(token)
        await session.commit()

        return sim
