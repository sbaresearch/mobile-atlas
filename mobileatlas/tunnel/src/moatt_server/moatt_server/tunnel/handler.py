import asyncio
import logging
import base64

from typing import Optional

import moatt_server.models as dbm
from moatt_server.auth import get_registration, valid
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from moatt_types.connect import AuthRequest, AuthResponse, AuthStatus, Token
from moatt_server.tunnel.util import write_msg

logger = logging.getLogger(__name__)

class Handler:
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout):
        self.async_session = async_session
        self.timeout = timeout

    async def _handle_auth(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Optional[tuple[Token, dbm.Provider]]:
        logger.debug("Waiting for authorisation message.")
        auth_req = AuthRequest.decode(await reader.readexactly(AuthRequest.LENGTH))
        logger.debug(f"Received authorisation message: {auth_req}")

        if auth_req == None:
            logger.warn("Received malformed authorisation message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return None

        provider = await get_registration(self.async_session, auth_req.session_token)
        if provider == None:
            logger.debug("Received an invalid session token. Closing connection.")
            await write_msg(writer, AuthResponse(AuthStatus.NotRegistered))
            writer.close()
            await writer.wait_closed()
            return

        try:
            token = Token(base64.b64decode(provider.token.value))
        except Exception as e:
            logger.error("Database contains an invalid token value.")
            raise e

        if not await valid(self.async_session, token):
            logger.debug("Received an invalid token. Closing connection.")
            await write_msg(writer, AuthResponse(AuthStatus.InvalidToken))
            writer.close()
            await writer.wait_closed()
            return
        else:
            logger.debug("Sending 'authorisation successful' status message.")
            await write_msg(writer, AuthResponse(AuthStatus.Success))

        return token, provider
