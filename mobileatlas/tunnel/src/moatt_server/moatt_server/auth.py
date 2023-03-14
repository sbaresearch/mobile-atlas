import logging
import secrets
import datetime

from typing import Optional
from moatt_types.connect import Imsi, Iccid, Token, IdentifierType, SessionToken
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
import moatt_server.models as dbm

logger = logging.getLogger(__name__)

def now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)

def generate_session_token() -> SessionToken:
    return SessionToken(secrets.token_bytes(25))

class AuthError(Exception):
    def __init__(self):
        super().__init__("Authorisation failure.")

def sync_valid(session: Session, token: Token) -> bool:
    logger.debug(f"'{token.as_base64()}'")
    result = session.get(dbm.Token, token.as_base64())
    logger.debug(result)

    if result == None:
        return False

    if result.active and result.value == token.as_base64():
        return True
    else:
        return False

def token_is_valid(token: dbm.Token) -> bool:
    assert type(token) == dbm.Token

    return token.active and not token_is_expired(token)

def token_is_expired(token: dbm.Token) -> bool:
    assert type(token) == dbm.Token

    return not (token.expires == None or token.expires > now())

def sessiontoken_is_valid(token: dbm.SessionToken) -> bool:
    assert type(token) == dbm.SessionToken

    return token_is_valid(token.token) and not sessiontoken_is_expired(token)

def sessiontoken_is_expired(token: dbm.SessionToken) -> bool:
    assert type(token) == dbm.SessionToken

    return not (token.expires == None or token.expires > now())

def sync_get_session(session: Session, session_token: SessionToken) -> Optional[dbm.SessionToken]:
    dbsess = session.get(dbm.SessionToken, session_token.as_base64())

    if dbsess == None or (dbsess.expires != None and dbsess.expires < now()):
        return None

    #dbsess.last_access = now # TODO isolation level
    #session.commit()
    return dbsess

async def get_sessiontoken(async_session: async_sessionmaker[AsyncSession], session_token: SessionToken) -> Optional[dbm.SessionToken]:
    assert type(session_token) == SessionToken

    stmt = select(dbm.SessionToken)\
            .where(dbm.SessionToken.value == session_token.as_base64())\
            .options(selectinload(dbm.SessionToken.provider))\
            .options(selectinload(dbm.SessionToken.token))
    async with async_session() as session:
        st = await session.scalar(stmt)

        if st == None:
            return None

        st.last_access = now()
        await session.commit()

    if sessiontoken_is_valid(st):
        return st
    else:
        return None

async def get_sim(async_session: async_sessionmaker[AsyncSession], session_token: dbm.SessionToken, identifier: Imsi | Iccid) -> Optional[dbm.Sim]:
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

            if sim == None or sim.provider_id == None:
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

            if sim == None or sim.provider_id == None:
                return None

            session.add(token)
            token.last_access = now()
            await session.commit()

            return sim
