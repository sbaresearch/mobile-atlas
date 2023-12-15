import datetime
import enum
import logging
import secrets
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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, selectinload

from . import models as dbm

logger = logging.getLogger(__name__)

# TODO: update token access information


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


def insert_new_session_token(
    session: Session, token_id, expires: Optional[datetime.timedelta] = None
) -> SessionToken:
    logger.debug("Creating new session token.")
    stoken = generate_session_token()
    n = now()

    session.add(
        dbm.SessionToken(
            value=stoken.as_base64(),
            created=n,
            last_access=now(),
            token_id=token_id,
            expires=n + expires if expires is not None else None,
        )
    )
    session.commit()

    return stoken


def deregister_session(session: Session, session_token: SessionToken) -> bool:
    stoken = session.get(dbm.SessionToken, session_token.as_base64())

    if stoken is None:
        return False

    if stoken.provider is not None:
        session.delete(stoken.provider)

    session.delete(stoken)
    session.commit()

    return True


def register_provider(
    session: Session, session_token: SessionToken, sims: dict[Iccid, Sim]
):
    stoken = session.get(dbm.SessionToken, session_token.as_base64())

    if stoken is None:
        # return False
        raise Exception()  # TODO

    if stoken.provider is None:
        provider = dbm.Provider(session_token_id=stoken.value)
        session.add(provider)
    else:
        provider = stoken.provider

    iccids = list(map(lambda x: x.iccid, sims.keys()))

    removed_sims = session.scalars(
        select(dbm.Sim)
        .where(dbm.Sim.provider_id == provider.id)
        .where(dbm.Sim.iccid.not_in(iccids))
    )

    for sim in removed_sims:
        sim.provider = None

    if len(sims) == 0:
        session.commit()
        return True

    existing_sims = list(
        session.scalars(select(dbm.Sim).where(dbm.Sim.iccid.in_(iccids)))
    )
    new_iccids = set(iccids).difference(set([sim.iccid for sim in existing_sims]))
    n = now()

    for sim in existing_sims:
        imsi = sims[Iccid(sim.iccid)].imsi.imsi

        if sim.provider is not None:
            if sim.provider.id == provider.id:
                continue

            if sim.provider.session_token.is_expired():
                deregister_session(session, sim.provider.session_token.to_con_type())
            elif sim.provider.allow_reregistration is False:
                # return Response(status=403)
                raise AuthError  # TODO

        sim.provider = provider
        session.add(dbm.Imsi(imsi=imsi, registered=n, sim=sim))

    for iccid in new_iccids:
        sim = dbm.Sim(
            iccid=iccid,
            imsi=[dbm.Imsi(imsi=sims[Iccid(iccid)].imsi.imsi, registered=n)],
            available=True,
            provider=provider,
        )
        session.add(sim)

    session.commit()


class AuthError(Exception):
    def __init__(self):
        super().__init__("Authorisation failure.")


def sync_valid(session: Session, token: Token) -> bool:
    result = session.get(dbm.Token, token.as_base64())

    if result is None:
        return False

    return result.is_valid()


def sync_get_session_token(
    session: Session, session_token: SessionToken
) -> Optional[dbm.SessionToken]:
    dbsess = session.get(dbm.SessionToken, session_token.as_base64())

    time = now()
    if dbsess is None or (dbsess.expires is not None and dbsess.expires < time):
        return None

    if dbsess.last_access < time:
        dbsess.last_access = time
        session.commit()

    return dbsess


# Async


async def log_apdu(
    async_session: async_sessionmaker[AsyncSession],
    sim_id: str,
    apdu: ApduPacket,
    sender: dbm.Sender,
):
    async with async_session() as session:
        async with session.begin():
            session.add(
                dbm.ApduLog(
                    sim_id=sim_id,
                    command=apdu.op,
                    payload=apdu.payload,
                    sender=sender,
                )
            )


async def get_sessiontoken(
    async_session: async_sessionmaker[AsyncSession], session_token: SessionToken
) -> dbm.SessionToken:
    assert type(session_token) == SessionToken

    stmt = (
        select(dbm.SessionToken)
        .where(dbm.SessionToken.value == session_token.as_base64())
        .options(selectinload(dbm.SessionToken.provider))
        .options(selectinload(dbm.SessionToken.token))
    )
    async with async_session() as session:
        st = await session.scalar(stmt)

        if st is None:
            raise TokenError(TokenErrorType.Invalid)

        st.last_access = now()
        await session.commit()

    if st.is_valid():
        return st
    elif st.is_expired():
        raise TokenError(TokenErrorType.Expired)
    else:
        raise TokenError(TokenErrorType.Invalid)


async def get_sim(
    async_session: async_sessionmaker[AsyncSession],
    session_token: dbm.SessionToken,
    identifier: Imsi | Iccid,
) -> Optional[dbm.Sim]:
    if not session_token.is_valid():
        raise AuthError

    token = session_token.token

    if identifier.identifier_type() == IdentifierType.Imsi:
        async with async_session() as session:
            imsi = identifier.imsi  # type: ignore
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
            token.last_access = now()
            await session.commit()

            return sim
    else:
        async with async_session() as session:
            iccid = identifier.iccid  # type: ignore
            stmt = (
                select(dbm.Sim)
                .where(dbm.Sim.iccid == iccid)
                .options(selectinload(dbm.Sim.provider))
            )
            sim = await session.scalar(stmt)

            if sim is None:
                return None

            session.add(token)
            token.last_access = now()
            await session.commit()

            return sim
