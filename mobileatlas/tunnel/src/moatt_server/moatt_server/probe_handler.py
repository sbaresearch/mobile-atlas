import asyncio
import logging

import connection_queue as connection_queue
from moatt_types.connect import AuthRequest, AuthStatus, ConnectStatus, AuthResponse, ConnectResponse
from util import read_con_req, write_msg
from auth import valid, find_provider, AuthError

logger = logging.getLogger(__name__)

class ProbeHandler:
    def __init__(self, timeout=0):
        self.timeout = timeout

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except:
            writer.close()
            await writer.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logger.debug("Waiting for probe auth req")
        auth_req = AuthRequest.decode(await reader.readexactly(AuthRequest.LENGTH))
        logger.debug(f"Got probe auth req {auth_req}")

        if auth_req == None:
            logger.warn("Received malformed authorisation message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return

        if not valid(auth_req.token):
            logger.debug("Received an invalid token. Closing connection.")
            await write_msg(writer, AuthResponse(AuthStatus.InvalidToken))
            writer.close()
            await writer.wait_closed()
            return
        else:
            logger.debug("Sending 'authorisation successful' status message.")
            await write_msg(writer, AuthResponse(AuthStatus.Success))

        logger.debug("waiting for probe connect request")
        con_req = await read_con_req(reader)
        logger.debug(f"got probe connect request {con_req}")

        if con_req == None:
            logger.warn("Received malformed connection request message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return

        try:
            provider_id = find_provider(auth_req.token, con_req.identifier)
        except AuthError:
            logger.debug("Received disallowed SIM request from probe. Closing connection.")
            await write_msg(writer, ConnectResponse(ConnectStatus.Forbidden))
            writer.close()
            await writer.wait_closed()
            return

        if provider_id == None:
            logger.debug("Probe requested unknown SIM. Closing connection.")
            await write_msg(writer, ConnectResponse(ConnectStatus.NotFound))
            writer.close()
            await writer.wait_closed()
            return

        #logger.debug("got successful probe con request. Sending success status.")
        #await write_msg(writer, ConnectResponse(ConnectStatus.Success))

        logger.debug("sending stream to provider handler")
        await connection_queue.put(provider_id, (con_req, auth_req.token, reader, writer))


