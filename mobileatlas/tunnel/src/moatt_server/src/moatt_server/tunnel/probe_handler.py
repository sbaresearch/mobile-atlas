import asyncio
import logging

from moatt_types.connect import (
    ConnectionRequestFlags,
    ConnectRequest,
    ConnectResponse,
    ConnectStatus,
    SessionToken,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .. import auth
from ..config import Config
from . import connection_queue
from .util import read_msg, write_msg

LOGGER = logging.getLogger(__name__)


class ProbeHandler:
    def __init__(self, config: Config, async_session: async_sessionmaker[AsyncSession]):
        self.config = config
        self.async_session = async_session

    async def valid_token(self, token: SessionToken) -> None:
        await auth.register_probe(token)

    async def handle(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        token: SessionToken,
    ) -> None:
        def cleanup():
            if not writer.is_closing():
                writer.close()

        try:
            await self._handle(reader, writer, token)
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
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        session_token: SessionToken,
    ) -> None:
        async def close():
            writer.close()
            await writer.wait_closed()

        LOGGER.debug("waiting for probe connect request")
        async with asyncio.timeout(
            self.config.PROBE_REQUEST_TIMEOUT.total_seconds()
            if self.config.PROBE_REQUEST_TIMEOUT
            else None
        ):
            con_req = await read_msg(reader, ConnectRequest.decode)
        LOGGER.debug(f"got probe connect request {con_req}")

        if con_req is None:
            LOGGER.warn(
                "Received malformed connection request message. Closing connection."
            )
            await close()
            return

        try:
            async with self.async_session() as session, session.begin():
                sim = await auth.get_sim(session, session_token, con_req.identifier)
        except auth.AuthError:
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

        probe_id = await auth.identity(session_token)
        assert probe_id is not None, (
            "Expected identity of probe to be known after" "successful registration."
        )

        try:
            connection_queue.put_nowait(
                sim.provider.id,
                connection_queue.QueueEntry(
                    sim,
                    probe_id,
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
