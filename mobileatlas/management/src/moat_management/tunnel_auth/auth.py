import base64
import binascii
import logging
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .. import config
from .. import models as dbm
from ..auth import get_basic_auth
from ..db import get_db
from . import models as pyd

LOGGER = logging.getLogger(__name__)

token = HTTPBearer()

Session = Annotated[AsyncSession, Depends(get_db)]

get_tunnel_basic_auth = get_basic_auth(
    config.get_config().TUNNEL_USER,
    base64.b64decode(config.get_config().TUNNEL_PW_SALT),
    base64.b64decode(config.get_config().TUNNEL_PW_HASH),
)


async def get_valid_token(
    session: Session, token: Annotated[HTTPAuthorizationCredentials, Depends(token)]
) -> dbm.MoAtToken:
    async with session.begin():
        try:
            token_bytes = base64.b64decode(token.credentials, validate=True)
        except binascii.Error as e:
            raise pyd.AuthException(pyd.AuthError.InvalidToken) from e

        return await is_valid_token(session, token_bytes)


async def generate_session_token(
    session: AsyncSession,
    scope: dbm.MoAtTokenScope,
    token: dbm.MoAtToken,
    *,
    probe_id: UUID | None = None,
    provider_id: UUID | None = None,
) -> dbm.SessionToken:
    if scope not in token.allowed_scope:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    stoken_value = secrets.token_bytes(32)

    stoken = dbm.SessionToken(
        value=stoken_value,
        token_id=token.id,
        scope=scope,
        probe_id=probe_id,
        provider_id=provider_id,
    )
    session.add(stoken)

    return stoken


async def generate_tunnel_token(
    session: AsyncSession,
    scope: dbm.MoAtTokenScope,
    admin: bool,
) -> dbm.MoAtToken:
    token_value = secrets.token_bytes(32)

    token = dbm.MoAtToken(value=token_value, allowed_scope=scope, admin=admin)
    session.add(token)

    return token


async def delete_session_token(session: AsyncSession, token: bytes) -> None:
    await session.execute(
        delete(dbm.SessionToken).where(dbm.SessionToken.value == token)
    )


async def is_valid_token(session: AsyncSession, token_bytes: bytes) -> dbm.MoAtToken:
    tok = await session.scalar(
        select(dbm.MoAtToken).where(dbm.MoAtToken.value == token_bytes)
    )

    if tok is None:
        LOGGER.debug(f"Found no token with matching value.")
        raise pyd.AuthException(pyd.AuthError.InvalidToken)

    if tok.expired():
        LOGGER.debug(f"Token expired.")
        raise pyd.AuthException(pyd.AuthError.ExpiredToken)

    return tok


async def get_valid_sess_token(session: Session, token: pyd.Token) -> dbm.SessionToken:
    async with session.begin():
        stok = await session.scalar(
            select(dbm.SessionToken)
            .options(selectinload(dbm.SessionToken.token))
            .where(dbm.SessionToken.value == token.root)
        )

        if stok is None:
            LOGGER.debug("Failed to find valid token.")
            raise pyd.AuthException(pyd.AuthError.InvalidToken)

        if stok.token.expired():
            LOGGER.debug("Token is expired.")
            raise pyd.AuthException(pyd.AuthError.ExpiredToken)

        return stok


async def get_valid_provider_token(
    stoken: Annotated[dbm.SessionToken, Depends(get_valid_sess_token)]
) -> dbm.SessionToken:
    if dbm.MoAtTokenScope.Provider in stoken.scope:
        return stoken

    raise pyd.AuthException(pyd.AuthError.InvalidToken)


async def get_valid_probe_token(
    stoken: Annotated[dbm.SessionToken, Depends(get_valid_sess_token)]
) -> dbm.SessionToken:
    if dbm.MoAtTokenScope.Probe in stoken.scope:
        return stoken

    raise pyd.AuthException(pyd.AuthError.InvalidToken)
