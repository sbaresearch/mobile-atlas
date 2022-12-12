import asyncio
import logging

import server.connection_queue as connection_queue
from server.apdu_stream import ApduStream
from tunnelTypes.connect import AuthRequest, AuthStatus, ConnectResponse, AuthResponse, ConnectStatus
from server.util import write_msg
from server.auth import valid

logger = logging.getLogger(__name__)

async def handle_established_connection(probe: ApduStream, provider: ApduStream):
    # TODO APDU logging
    probe_task = asyncio.create_task(probe.recv(), name="probe")
    provider_task = asyncio.create_task(provider.recv(), name="provider")
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

                probe_task.cancel()
                provider_task.cancel()
                await probe.close()
                await provider.close()
                return
            except ValueError:
                logger.warn(f"Received a malformed packet. Closing connections.")
                probe_task.cancel()
                provider_task.cancel()
                await probe.close()
                await provider.close()
                return

            if r == None:
                logger.info(f"{t.get_name()} closed the connection.")
                probe_task.cancel()
                provider_task.cancel()
                await probe.close()
                await provider.close()
                return

            if t.get_name() == "probe":
                provider.send_background(r)
                probe_task = asyncio.create_task(probe.recv(), name="probe")
            elif t.get_name() == "provider":
                probe.send_background(r)
                provider_task = asyncio.create_task(provider.recv(), name="provider")


class ProviderHandler:
    def __init__(self, timeout=0):
        self.timeout = timeout

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except:
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

        if not valid(auth_req.token):
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
            con_req, probe_token, probe_reader, probe_writer = await connection_queue.get(
                    auth_req.identifier
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

        probe_stream = ApduStream(probe_token, probe_reader, probe_writer)
        provider_stream = ApduStream(auth_req.token, reader, writer)

        try:
            await handle_established_connection(probe_stream, provider_stream)
        finally:
            await provider_stream.close()
            await probe_stream.close()
