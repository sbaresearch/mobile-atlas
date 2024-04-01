import base64
import binascii
import secrets
from collections.abc import Callable, Coroutine
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models as dbm
from .config import get_config
from .db import get_db

_basic_auth = HTTPBasic()


async def get_basic_auth(
    creds: Annotated[HTTPBasicCredentials, Depends(_basic_auth)]
) -> str:
    correct_username = secrets.compare_digest(
        creds.username.encode("utf-8"), get_config().BASIC_AUTH_USER.encode("utf-8")
    )
    correct_password = secrets.compare_digest(
        creds.password.encode("utf-8"), get_config().BASIC_AUTH_PASSWORD.encode("utf-8")
    )

    if correct_username and correct_password:
        return creds.username

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password.",
        headers={"WWW-Authenticate": "Basic"},
    )


_bearer_creds = HTTPBearer()


def _bearer_token(
    scope: dbm.TokenScope,
) -> Callable[..., Coroutine[None, None, dbm.MamToken]]:
    async def _bearer_token(
        creds: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_creds)],
        session: Annotated[AsyncSession, Depends(get_db)],
    ) -> dbm.MamToken:
        async with session.begin():
            token = await check_token(session, creds.credentials, scope)

            if token is not None:
                session.add(
                    dbm.MamTokenAccessLog(
                        token=token,
                        token_value=token.token_value(),
                        scope=scope,
                        action=dbm.TokenAction.Access,
                    )
                )
                return token

            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return _bearer_token


bearer_token_any = _bearer_token(dbm.TokenScope(0))
bearer_token_wg = _bearer_token(dbm.TokenScope.Wireguard)
bearer_token_probe = _bearer_token(dbm.TokenScope.Probe)


async def check_token(
    session: AsyncSession, token: str, scope: dbm.TokenScope
) -> dbm.MamToken:
    token = validate_token(token)

    mamtoken = await session.scalar(
        select(dbm.MamToken).where(dbm.MamToken.token == token)
    )

    if mamtoken is not None and scope in mamtoken.scope:
        return mamtoken

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)


def validate_token(token: str) -> str:
    try:
        if not token.isascii() or len(base64.b64decode(token, validate=True)) != 32:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    except binascii.Error as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from e

    return token
