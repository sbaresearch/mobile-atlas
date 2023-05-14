import logging
import secrets
import datetime

from typing import Optional
from moatt_types.connect import Imsi, Iccid, Token, IdentifierType, SessionToken, ApduPacket
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
import moatt_server.models as dbm

logger = logging.getLogger(__name__)

# TODO: look into the possibility of timing attacks

class Sim:
    def __init__(self, iccid: Iccid, imsi: Imsi):
        self.iccid = iccid
        self.imsi = imsi

def now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)

def generate_session_token() -> SessionToken:
    return SessionToken(secrets.token_bytes(25))

def insert_new_session_token(session: Session, token_id) -> SessionToken:
    logger.debug("Creating new session token.")
    stoken = generate_session_token()

    session.add(dbm.SessionToken(
        value=stoken.as_base64(),
        created=now(),
        last_access=now(),
        token_id=token_id,
        ))
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

def register_provider(session: Session, session_token: SessionToken, sims: dict[Iccid, Sim]):
    stoken = session.get(dbm.SessionToken, session_token.as_base64())

    if stoken is None:
        #return False
        raise Exception()

    if stoken.provider is None:
        provider = dbm.Provider(
                session_token_id=stoken.value
                )
        session.add(provider)
    else:
        provider = stoken.provider

    iccids = list(map(lambda x: x.iccid, sims.keys()))

    removed_sims = session.scalars(
            select(dbm.Sim)\
                    .where(dbm.Sim.provider_id == provider.id)\
                    .where(dbm.Sim.iccid.not_in(iccids))
            )

    for sim in removed_sims:
        sim.provider = None

    if len(sims) == 0:
        session.commit()
        return True

    existing_sims = list(session.scalars(select(dbm.Sim).where(dbm.Sim.iccid.in_(iccids))))
    new_iccids = set(iccids).difference(set([sim.iccid for sim in existing_sims]))
    n = now()

    for sim in existing_sims:
        imsi = sims[Iccid(sim.iccid)].imsi.imsi

        if sim.provider is not None:
            if sim.provider.id == provider.id:
                continue

            if sim.provider.allow_reregistration is False:
                #return Response(status=403)
                raise AuthError

        sim.provider = provider
        session.add(dbm.Imsi(imsi=imsi,registered=n,sim=sim))

    for iccid in new_iccids:
        sim = dbm.Sim(
                iccid=iccid,
                imsi=[dbm.Imsi(imsi=sims[Iccid(iccid)].imsi.imsi, registered=n)],
                available=True,
                provider=provider
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

    return token_is_valid(result)

def token_is_valid(token: dbm.Token) -> bool:
    assert type(token) == dbm.Token

    return token.active and not token_is_expired(token)

def token_is_expired(token: dbm.Token) -> bool:
    assert type(token) == dbm.Token

    return not (token.expires is None or token.expires > now())

def sessiontoken_is_valid(token: dbm.SessionToken) -> bool:
    assert type(token) == dbm.SessionToken

    return token_is_valid(token.token) and not sessiontoken_is_expired(token)

def sessiontoken_is_expired(token: dbm.SessionToken) -> bool:
    assert type(token) == dbm.SessionToken

    return not (token.expires is None or token.expires > now())

def sync_get_session_token(
        session: Session,
        session_token: SessionToken
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
        sender: dbm.Sender
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
        async_session: async_sessionmaker[AsyncSession],
        session_token: SessionToken
        ) -> Optional[dbm.SessionToken]:
    assert type(session_token) == SessionToken

    stmt = select(dbm.SessionToken)\
            .where(dbm.SessionToken.value == session_token.as_base64())\
            .options(selectinload(dbm.SessionToken.provider))\
            .options(selectinload(dbm.SessionToken.token))
    async with async_session() as session:
        st = await session.scalar(stmt)

        if st is None:
            return None

        st.last_access = now()
        await session.commit()

    if sessiontoken_is_valid(st):
        return st
    else:
        return None

async def get_sim(
        async_session: async_sessionmaker[AsyncSession],
        session_token: dbm.SessionToken,
        identifier: Imsi | Iccid
        ) -> Optional[dbm.Sim]:
    if not sessiontoken_is_valid(session_token):
        raise AuthError

    token = session_token.token

    if identifier.identifier_type() == IdentifierType.Imsi:
        async with async_session() as session:
            imsi = identifier.imsi # type: ignore
            stmt = select(dbm.Sim)\
                    .join(dbm.Sim.imsi)\
                    .where(dbm.Imsi.imsi == imsi)\
                    .order_by(dbm.Imsi.id.desc())\
                    .limit(1)\
                    .options(selectinload(dbm.Sim.provider))
            sim = await session.scalar(stmt)

            if sim is None:
                return None

            session.add(token)
            token.last_access = now()
            await session.commit()

            return sim
    else:
        async with async_session() as session:
            iccid = identifier.iccid # type: ignore
            stmt = select(dbm.Sim)\
                    .where(dbm.Sim.iccid == iccid)\
                    .options(selectinload(dbm.Sim.provider))
            sim = await session.scalar(stmt)

            if sim is None:
                return None

            session.add(token)
            token.last_access = now()
            await session.commit()

            return sim
