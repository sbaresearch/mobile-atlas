import base64
import binascii
import logging
from typing import Annotated, Optional

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer
from moatt_types.connect import SessionToken, Token
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_session_token, valid_token
from .db import get_db

LOGGER = logging.getLogger(__name__)

_session_token_optional = APIKeyCookie(name="session_token", auto_error=False)


async def session_token_optional(
    stoken: Annotated[str, Depends(_session_token_optional)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[SessionToken]:
    if stoken is None:
        return None

    async with session.begin():
        session_token = await get_session_token(session, _parse_session_token(stoken))
        return session_token.to_con_type()


async def session_token(
    stoken: Annotated[Optional[SessionToken], Depends(session_token_optional)]
) -> SessionToken:
    if stoken is None:
        raise HTTPException(status_code=401)

    return stoken


def _parse_session_token(stoken: str) -> SessionToken:
    try:
        session_token = SessionToken(base64.b64decode(stoken, validate=True))
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=401)

    return session_token


_token = HTTPBearer()


async def token(
    tok: Annotated[HTTPAuthorizationCredentials, Depends(_token)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    try:
        token = Token(base64.b64decode(tok.credentials, validate=True))
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=401)

    async with session.begin():
        valid = await valid_token(session, token)

    if valid:
        return token
    else:
        raise HTTPException(status_code=403)
