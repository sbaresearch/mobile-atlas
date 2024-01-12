import asyncio
import base64
import binascii
import logging
from typing import Optional

from moatt_types.connect import AuthRequest, AuthResponse, SessionToken
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .. import config
from .. import models as dbm
from ..auth import TokenError, get_session_token
from .util import write_msg

LOGGER = logging.getLogger(__name__)
CONFIG = config.get_config()


class Handler:
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout):
        self.async_session = async_session
        self.timeout = timeout

    async def _handle_auth_req(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> Optional[dbm.SessionToken]:
        LOGGER.debug("Waiting for authorisation message.")
        async with asyncio.timeout(CONFIG.AUTHMSG_TIMEOUT):
            auth_req = AuthRequest.decode(await reader.readexactly(AuthRequest.LENGTH))
        LOGGER.debug(f"Received authorisation message: {auth_req}")

        if auth_req is None:
            LOGGER.warn("Received malformed authorisation message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return None

        try:
            async with self.async_session() as session, session.begin():
                session_token = await get_session_token(session, auth_req.session_token)
        except TokenError as e:
            LOGGER.debug(
                f"Received an invalid session token. Closing connection. (Reason: {e.etype})"
            )
            await write_msg(writer, AuthResponse(e.to_auth_status()))
            writer.close()
            await writer.wait_closed()
            return None

        try:
            SessionToken(base64.b64decode(session_token.value, validate=True))
        except (binascii.Error, ValueError):
            LOGGER.error("Database contains an invalid token value.")
            raise AssertionError("Database contains an invalid token value.")

        return session_token
