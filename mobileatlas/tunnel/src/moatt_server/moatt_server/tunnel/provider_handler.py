import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import moatt_server.tunnel.connection_queue as connection_queue
from moatt_server.tunnel.apdu_stream import ApduStream
from moatt_types.connect import AuthRequest, AuthStatus, ConnectResponse, AuthResponse, ConnectStatus
import moatt_server.models as dbm
from moatt_server.tunnel.util import write_msg
from moatt_server.auth import valid, get_registration

logger = logging.getLogger(__name__)

class ProviderHandler:
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout=0):
        self.async_session = async_session
        self.timeout = timeout

    async def handle_established_connection(self, probe: ApduStream, provider: ApduStream):
        # TODO APDU logging
        probe_task = asyncio.create_task(probe.recv(), name="probe")
        provider_task = asyncio.create_task(provider.recv(), name="provider")

        async def cleanup() -> None:
            probe_task.cancel()
            provider_task.cancel()
            await probe.close()
            await provider.close()

        while True:
            done, pending = await asyncio.wait([probe_task, provider_task], return_when=asyncio.FIRST_COMPLETED)

            assert len(done) > 0 and len(done) <= 2
            assert len(pending) >= 0 and len(pending) < 2
            for t in done:
                try:
                    r = t.result()
                except asyncio.IncompleteReadError as e:
                    logger.warn(f"Unexpected EOF while trying to read from {t.get_name()} connection."
                                f"(expected at least {e.expected} more bytes.)")

                    await cleanup()
                    return
                except ValueError:
                    logger.warn(f"Received a malformed packet. Closing connections.")
                    await cleanup()
                    return

                if r == None:
                    logger.info(f"{t.get_name()} closed the connection.")
                    await cleanup()
                    return

                async with self.async_session() as session:
                    async with session.begin():
                        session.add(
                                dbm.ApduLog(
                                    sim_id=probe.iccid.iccid,
                                    command=r.op,
                                    payload=r.payload,
                                    sender=dbm.Sender.Probe if t.get_name() == "probe" else dbm.Sender.Provider,
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
            logger.warn(f"Exception occured while handling connection: {e}")
            writer.close()
            await writer.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        logger.debug("Waiting for authorisation message.")
        auth_req = AuthRequest.decode(await reader.readexactly(AuthRequest.LENGTH))
        logger.debug(f"Got authorisation packet: {auth_req}")

        if auth_req == None:
            logger.warn("Received malformed authorisation message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return

        provider = await get_registration(self.async_session, auth_req.session_token)
        if provider == None:
            logger.debug("Received an invalid session token. Closing connection.")
            await write_msg(writer, AuthResponse(AuthStatus.NotRegistered))
            writer.close()
            await writer.wait_closed()
            return

        if not await valid(self.async_session, auth_req.token):
            logger.debug("Received an invalid token. Closing connection.")
            await write_msg(writer, AuthResponse(AuthStatus.InvalidToken))
            writer.close()
            await writer.wait_closed()
            return
        else:
            logger.debug("Sending 'authorisation successful' status message.")
            await write_msg(writer, AuthResponse(AuthStatus.Success))

        while True:
            logger.debug("waiting for connection request.")
            iccid, con_req, probe_token, probe_reader, probe_writer = await connection_queue.get(
                    provider.id
                    )

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

        if con_res == None:
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

        # TODO
        probe_stream = ApduStream(iccid, probe_token, probe_reader, probe_writer)
        provider_stream = ApduStream(iccid, auth_req.token, reader, writer)

        try:
            await self.handle_established_connection(probe_stream, provider_stream)
        finally:
            await provider_stream.close()
            await probe_stream.close()
