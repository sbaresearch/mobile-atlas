import asyncio
import logging
import traceback

from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
import moatt_server.tunnel.connection_queue as connection_queue
from moatt_types.connect import ConnectStatus, ConnectResponse, AuthResponse, AuthStatus
from moatt_server.tunnel.util import read_con_req, write_msg
from moatt_server.auth import get_sim, AuthError
from moatt_server.tunnel.handler import Handler

logger = logging.getLogger(__name__)

class ProbeHandler(Handler):
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout=0):
        super().__init__(async_session, timeout)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except (EOFError, ConnectionResetError):
            logger.info("Client closed connection unexpectedly.")
        except Exception:
            if not writer.is_closing():
                writer.close()

            logger.error(traceback.format_exc())

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        session_token = await self._handle_auth_req(reader, writer)

        if session_token is None:
            return

        logger.debug("Sending successful authorisation message.")
        await write_msg(writer, AuthResponse(AuthStatus.Success))

        logger.debug("waiting for probe connect request")
        con_req = await read_con_req(reader)
        logger.debug(f"got probe connect request {con_req}")

        if con_req is None:
            logger.warn("Received malformed connection request message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return

        try:
            sim = await get_sim(self.async_session, session_token, con_req.identifier)
        except AuthError:
            logger.debug("Received disallowed SIM request from probe. Closing connection.")
            await write_msg(writer, ConnectResponse(ConnectStatus.Forbidden))
            writer.close()
            await writer.wait_closed()
            return

        if sim is None:
            logger.debug("Probe requested unknown SIM. Closing connection.")
            await write_msg(writer, ConnectResponse(ConnectStatus.NotFound))
            writer.close()
            await writer.wait_closed()
            return

        if sim.provider is None:
            logger.debug("Requested SIM is unavailable. Closing connection.")
            await write_msg(writer, ConnectResponse(ConnectStatus.NotAvailable))
            writer.close()
            await writer.wait_closed()
            return

        logger.debug("Sending stream to provider handler")
        await connection_queue.put(sim.provider.id, (sim, con_req, reader, writer))
