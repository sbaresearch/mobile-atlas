import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
import moatt_server.tunnel.connection_queue as connection_queue
from moatt_types.connect import ConnectStatus, ConnectResponse
from moatt_server.tunnel.util import read_con_req, write_msg
from moatt_server.auth import find_provider, AuthError
from moatt_server.tunnel.handler import Handler

logger = logging.getLogger(__name__)

class ProbeHandler(Handler):
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout=0):
        super().__init__(async_session, timeout)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except:
            writer.close()
            await writer.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        provider = await self._handle_auth(reader, writer)

        if provider == None:
            return

        token, provider = provider

        logger.debug("waiting for probe connect request")
        con_req = await read_con_req(reader)
        logger.debug(f"got probe connect request {con_req}")

        if con_req == None:
            logger.warn("Received malformed connection request message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return

        try:
            provider_id, iccid = await find_provider(self.async_session, token, con_req.identifier)
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

        logger.debug("Sending stream to provider handler")
        await connection_queue.put(provider_id, (iccid, con_req, token, reader, writer))
