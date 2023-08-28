import asyncio
import logging
import base64
import binascii

from typing import Optional

import moatt_server.models as dbm
from moatt_server.auth import get_sessiontoken, TokenError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from moatt_types.connect import AuthRequest, AuthResponse, SessionToken
from moatt_server.tunnel.util import write_msg

import moatt_server.config as config

logger = logging.getLogger(__name__)

class Handler:
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout):
        self.async_session = async_session
        self.timeout = timeout

    async def _handle_auth_req(
            self,
            reader: asyncio.StreamReader,
            writer: asyncio.StreamWriter
            ) -> Optional[dbm.SessionToken]:
        logger.debug("Waiting for authorisation message.")
        async with asyncio.timeout(config.AUTHMSG_TIMEOUT):
            auth_req = AuthRequest.decode(await reader.readexactly(AuthRequest.LENGTH))
        logger.debug(f"Received authorisation message: {auth_req}")

        if auth_req is None:
            logger.warn("Received malformed authorisation message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return None

        try:
            session_token = await get_sessiontoken(self.async_session, auth_req.session_token)
        except TokenError as e:
            logger.debug(f"Received an invalid session token. Closing connection. (Reason: {e.etype})")
            await write_msg(writer, AuthResponse(e.to_auth_status()))
            writer.close()
            await writer.wait_closed()
            return None

        try:
            SessionToken(base64.b64decode(session_token.value, validate=True))
        except (binascii.Error, ValueError):
            logger.error("Database contains an invalid token value.")
            raise AssertionError("Database contains an invalid token value.")

        return session_token
