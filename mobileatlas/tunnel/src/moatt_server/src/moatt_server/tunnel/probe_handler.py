import asyncio
import logging

from moatt_types.connect import (
    AuthResponse,
    AuthStatus,
    ConnectionRequestFlags,
    ConnectResponse,
    ConnectStatus,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .. import config
from ..auth import AuthError, get_sim
from . import connection_queue
from .handler import Handler
from .util import read_con_req, write_msg

LOGGER = logging.getLogger(__name__)


class ProbeHandler(Handler):
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout=0):
        super().__init__(async_session, timeout)

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        def cleanup():
            if not writer.is_closing():
                writer.close()

        try:
            await self._handle(reader, writer)
        except (EOFError, ConnectionResetError):
            LOGGER.warn("Client closed connection unexpectedly.")
            cleanup()
        except TimeoutError:
            LOGGER.warn("Connection timed out.")
            cleanup()
        except Exception as e:
            LOGGER.warn(f"Exception occurred while handling connection.\n{e}")
            cleanup()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        async def close():
            writer.close()
            await writer.wait_closed()

        session_token = await self._handle_auth_req(reader, writer)

        if session_token is None:
            return

        LOGGER.debug("Sending successful authorisation message.")
        await write_msg(writer, AuthResponse(AuthStatus.Success))

        LOGGER.debug("waiting for probe connect request")
        async with asyncio.timeout(config.get_config().PROBE_REQUEST_TIMEOUT):
            con_req = await read_con_req(reader)
        LOGGER.debug(f"got probe connect request {con_req}")

        if con_req is None:
            LOGGER.warn(
                "Received malformed connection request message. Closing connection."
            )
            await close()
            return

        try:
            async with self.async_session() as session, session.begin():
                sim = await get_sim(session, session_token, con_req.identifier)
        except AuthError:
            LOGGER.debug(
                "Received disallowed SIM request from probe. Closing connection."
            )
            await write_msg(writer, ConnectResponse(ConnectStatus.Forbidden))
            await close()
            return

        if sim is None:
            LOGGER.debug("Probe requested unknown SIM. Closing connection.")
            await write_msg(writer, ConnectResponse(ConnectStatus.NotFound))
            await close()
            return

        if sim.provider is None:
            LOGGER.debug("Requested SIM is unknown. Closing connection.")
            await write_msg(writer, ConnectResponse(ConnectStatus.NotAvailable))
            await close()
            return

        LOGGER.debug("Sending stream to provider handler")
        try:
            connection_queue.put_nowait(
                sim.provider.id,
                connection_queue.QueueEntry(
                    sim,
                    con_req,
                    reader,
                    writer,
                    immediate=ConnectionRequestFlags.NO_WAIT in con_req.flags,
                ),
            )
        except asyncio.QueueFull:
            if ConnectionRequestFlags.NO_WAIT in con_req.flags:
                LOGGER.info(
                    f"Requested SIM card is not immediately available. {sim.iccid=}"
                )
            else:
                LOGGER.warn(f"Queue for provider is full. {sim.provider.id=}")
            await write_msg(writer, ConnectResponse(ConnectStatus.NotAvailable))
            await close()
