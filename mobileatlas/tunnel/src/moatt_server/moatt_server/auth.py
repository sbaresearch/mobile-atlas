import json
import logging
import secrets

from typing import Optional
from moatt_types.connect import Imsi, Iccid, Token, IdentifierType, SessionToken
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
#from moatt_server.models import Sim, Imsi, Provider, Token as DBToken
import moatt_server.models as dbm

logger = logging.getLogger(__name__)

def generate_session_token() -> SessionToken:
    return SessionToken(secrets.token_bytes(25))

def read_tokens(filename="tokens.json"):
    with open(filename, "r") as f:
        return list(map(lambda x: Token(bytes.fromhex(x)), json.load(f)))

def read_provider_mapping(filename="prov_map.json"):
    with open(filename, "r") as f:
        res = json.load(f)
    return res

#valid_tokens = read_tokens()
#sim_provider_mapping = read_provider_mapping()

class AuthError(Exception):
    def __init__(self):
        super().__init__("Authorisation failure.")

# TODO: combine sync_valid and valid
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

async def valid(async_session: async_sessionmaker[AsyncSession], token: Token) -> bool:
    async with async_session() as session:
        result = await session.get(dbm.Token, token.as_base64())

        if result == None:
            logger.debug("token none")
            return False
        
        logger.debug(result)
        logger.debug(token)
        if result.active and result.value == token.as_base64():
            return True
        else:
            return False

async def allowed_sim_request(async_session: async_sessionmaker[AsyncSession], token: Token, identifier: Imsi | Iccid) -> bool:
    if not await valid(async_session, token):
        raise AuthError

    id(identifier)
    return True

def sync_get_registration(session: Session, session_token: SessionToken) -> Optional[dbm.Provider]:
    assert type(session_token) == SessionToken

    logger.debug(f"Session token: '{session_token.as_base64()}'")
    stmt = select(dbm.Provider).where(dbm.Provider.session_token == session_token.as_base64())
    provider = session.scalar(stmt)

    if not _check_is_registered(provider, session_token):
        return None

    return provider

def sync_is_registered(session: Session, session_token: SessionToken) -> bool:
    assert type(session_token) == SessionToken

    logger.debug(f"Session token: '{session_token.as_base64()}'")
    stmt = select(dbm.Provider).where(dbm.Provider.session_token == session_token.as_base64())
    provider = session.scalar(stmt)

    return _check_is_registered(provider, session_token)

def _check_is_registered(provider: dbm.Provider | None, session_token: SessionToken) -> bool:
    if provider == None:
        logger.debug("Provider is none")
        return False

    logger.debug(provider.session_token)
    logger.debug(session_token)

    if provider.session_token == session_token.as_base64():
        return True
    else:
        return False

async def get_registration(async_session: async_sessionmaker[AsyncSession], session_token: SessionToken) -> Optional[dbm.Provider]:
    assert type(session_token) == SessionToken

    stmt = select(dbm.Provider)\
            .where(dbm.Provider.session_token == session_token.as_base64())\
            .options(selectinload(dbm.Provider.token))
    async with async_session() as session:
        provider = await session.scalar(stmt)

    if not _check_is_registered(provider, session_token):
        return None
    else:
        return provider

async def is_registered(async_session: async_sessionmaker[AsyncSession], session_token: SessionToken) -> bool:
    assert type(session_token) == SessionToken

    async with async_session() as session:
        stmt = select(dbm.Provider).where(dbm.Provider.session_token == session_token.as_base64())
        provider = await session.scalar(stmt)

    return _check_is_registered(provider, session_token)

async def find_provider(async_session: async_sessionmaker[AsyncSession], token: Token, identifier: Imsi | Iccid) -> tuple[Optional[int], Optional[Iccid]]:
    if not await allowed_sim_request(async_session, token, identifier):
        raise AuthError

    if identifier.identifier_type() == IdentifierType.Imsi:
        async with async_session() as session:
            stmt = select(dbm.Sim).join(dbm.Sim.imsi).order_by(dbm.Imsi.registered.desc()).limit(1)
            sim = await session.scalar(stmt)

            if sim == None:
                return None, None

            return sim.provider_id, Iccid(sim.iccid)
        #return sim_provider_mapping["imsi"].get(identifier.imsi)
    else:
        async with async_session() as session:
            sim = await session.get(dbm.Sim, identifier.iccid)

            if sim == None:
                return None, None

            return sim.provider_id, sim.iccid
