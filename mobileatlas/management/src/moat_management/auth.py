import base64
import binascii
import hashlib
import logging
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

LOGGER = logging.getLogger(__name__)


def get_basic_auth(username: str, pw_salt: bytes, pw_hash: bytes):
    async def f(creds: Annotated[HTTPBasicCredentials, Depends(_basic_auth)]) -> str:
        cfg = get_config()

        correct_username = secrets.compare_digest(
            creds.username.encode("utf-8"), username.encode("utf-8")
        )
        hashed_pw = hashlib.scrypt(
            creds.password.encode("utf-8"),
            salt=pw_salt,
            n=cfg.SCRYPT_COST,
            r=cfg.SCRYPT_BLOCK_SIZE,
            p=cfg.SCRYPT_PARALLELIZATION,
        )
        correct_password = secrets.compare_digest(hashed_pw, pw_hash)

        if correct_username and correct_password:
            return creds.username

        LOGGER.warning(f"Authentication failed for user: {creds.username}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Basic"},
        )

    return f


get_basic_auth_admin = get_basic_auth(
    get_config().BASIC_AUTH_USER,
    base64.b64decode(get_config().BASIC_AUTH_PW_SALT),
    base64.b64decode(get_config().BASIC_AUTH_PW_HASH),
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
