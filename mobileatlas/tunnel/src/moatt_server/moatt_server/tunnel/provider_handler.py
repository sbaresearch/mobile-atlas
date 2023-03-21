import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import moatt_server.tunnel.connection_queue as connection_queue
from moatt_server.tunnel.apdu_stream import ApduStream
from moatt_types.connect import ConnectResponse, ConnectStatus, AuthResponse, AuthStatus
import moatt_server.models as dbm
from moatt_server.tunnel.util import write_msg
from moatt_server.tunnel.handler import Handler

logger = logging.getLogger(__name__)

class ProviderHandler(Handler):
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout=0):
        super().__init__(async_session, timeout)

    async def handle_established_connection(self, probe: ApduStream, provider: ApduStream):
        probe_task = asyncio.create_task(probe.recv(), name="probe")
        provider_task = asyncio.create_task(provider.recv(), name="provider")

        async def cleanup() -> None:
            probe_task.cancel()
            provider_task.cancel()
            await probe.close()
            await provider.close()

        while True:
            done, pending = await asyncio.wait(
                    [probe_task, provider_task],
                    return_when=asyncio.FIRST_COMPLETED
                    )

            assert len(done) > 0 and len(done) <= 2
            assert len(pending) >= 0 and len(pending) < 2
            for t in done:
                try:
                    r = t.result()
                except asyncio.IncompleteReadError as e:
                    logger.warn(f"Unexpected EOF while trying to read from {t.get_name()} "
                                f"connection. (expected at least {e.expected} more bytes.)")

                    await cleanup()
                    return
                except ValueError:
                    logger.warn("Received a malformed packet. Closing connections.")
                    await cleanup()
                    return

                if r is None:
                    logger.info(f"{t.get_name()} closed the connection.")
                    await cleanup()
                    return

                async with self.async_session() as session:
                    async with session.begin():
                        session.add(
                                dbm.ApduLog(
                                    sim_id=probe.sim.iccid,
                                    command=r.op,
                                    payload=r.payload,
                                    sender=dbm.Sender.Probe if t.get_name() == "probe"\
                                                            else dbm.Sender.Provider,
                                    )
                                )

                if t.get_name() == "probe":
                    provider.send_background(r)
                    probe_task = asyncio.create_task(probe.recv(), name="probe")
                elif t.get_name() == "provider":
                    probe.send_background(r)
                    provider_task = asyncio.create_task(provider.recv(), name="provider")

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except Exception as e:
            logger.warn(f"Exception occurred while handling connection: {e}")
            writer.close()
            await writer.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        session_token = await self._handle_auth_req(reader, writer)

        if session_token is None:
            return

        if session_token.provider is None:
            logger.debug("Provider has not registered any Sim cards.")
            return

        await write_msg(writer, AuthResponse(AuthStatus.Success))

        while True:
            logger.debug("waiting for connection request.")
            sim, con_req, probe_reader, probe_writer = await connection_queue.get(
                    session_token.provider.id
                    )

            if reader.at_eof():
                logger.info("Provider disconnected.")
                await connection_queue.put(
                        session_token.provider.id,
                        (sim, con_req, probe_reader, probe_writer)
                        )
                writer.close()
                await writer.wait_closed()
                return

            if probe_reader.at_eof():
                logger.warn("Probe disconnected early. Waiting for new request.")
                probe_writer.close()
                await probe_writer.wait_closed()
                continue
            else:
                break

        logger.debug(f"Received a connection request: {con_req}")

        await write_msg(writer, con_req)

        logger.debug("Waiting for provider to accept connection request.")
        con_res = ConnectResponse.decode(await reader.readexactly(ConnectResponse.LENGTH))
        logger.debug(f"Received a response for a connection request: {con_res}")

        if con_res is None:
            logger.warn("Received malformed connection request status. Closing connections.")
            writer.close()
            await writer.wait_closed()
            probe_writer.close()
            await probe_writer.wait_closed()
            return

        logger.debug("Forwarding connection request status to probe.")
        await write_msg(probe_writer, con_res)

        if con_res.status != ConnectStatus.Success:
            logger.debug("Received unsuccessful connection status response. Closing connections.")
            writer.close()
            await writer.wait_closed()
            probe_writer.close()
            await probe_writer.wait_closed()
            return

        probe_stream = ApduStream(sim, probe_reader, probe_writer)
        provider_stream = ApduStream(sim, reader, writer)

        try:
            await self.handle_established_connection(probe_stream, provider_stream)
        finally:
            await provider_stream.close()
            await probe_stream.close()
