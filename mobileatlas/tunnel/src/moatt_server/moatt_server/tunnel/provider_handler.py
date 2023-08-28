import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import moatt_server.tunnel.connection_queue as connection_queue
from moatt_server.tunnel.apdu_stream import ApduStream
from moatt_types.connect import ConnectResponse, ConnectStatus, AuthResponse, AuthStatus
import moatt_server.models as dbm
import moatt_server.auth as auth
from moatt_server.tunnel.util import write_msg, poll_eof
from moatt_server.tunnel.handler import Handler

import moatt_server.config as config

logger = logging.getLogger(__name__)

class ProviderHandler(Handler):
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout=0):
        super().__init__(async_session, timeout)

    async def handle_established_connection(self, probe: ApduStream, provider: ApduStream):
        probe_task = asyncio.create_task(probe.recv(), name="probe")
        provider_task = asyncio.create_task(provider.recv(), name="provider")

        try:
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

                        return
                    except ValueError:
                        logger.warn("Received a malformed packet. Closing connections.")
                        return

                    if r is None:
                        logger.info(f"{t.get_name()} closed the connection.")
                        return

                    await auth.log_apdu(
                            self.async_session,
                            probe.sim.iccid,
                            r,
                            dbm.Sender.Probe if t.get_name() == "probe" else dbm.Sender.Provider
                            )

                    if t.get_name() == "probe":
                        provider.send_background(r)
                        probe_task = asyncio.create_task(probe.recv(), name="probe")
                    elif t.get_name() == "provider":
                        probe.send_background(r)
                        provider_task = asyncio.create_task(provider.recv(), name="provider")
        finally:
            probe_task.cancel()
            provider_task.cancel()
            await probe.close()
            await provider.close()

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await self._handle(reader, writer)
        except (EOFError, ConnectionResetError):
            logger.warn("Client closed connection unexpectedly.")
        except TimeoutError as e:
            logger.warn(f"Connection timed out.")
        except Exception as e:
            logger.warn(f"Exception occurred while handling connection: {e}")
        finally:
            if not writer.is_closing():
                writer.close()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        session_token = await self._handle_auth_req(reader, writer)

        assert session_token is not None

        if session_token.provider is None:
            logger.debug("Session token was not used to register a provider.")
            await write_msg(writer, AuthResponse(AuthStatus.ProviderNotRegistered))
            writer.close()
            await writer.wait_closed()
            return

        await write_msg(writer, AuthResponse(AuthStatus.Success))

        provider_id = session_token.provider.id
        while True:
            logger.debug("waiting for connection request.")
            q_task = asyncio.create_task(connection_queue.get(provider_id), name="q")

            # poll whether the provider is still connected
            # in order to prevent a buildup of tasks that
            # cannot make progress but wait on a connection request to arrive regardless
            eof_task = asyncio.create_task(poll_eof(writer), name="eof")

            done, _ = await asyncio.wait([q_task, eof_task], return_when=asyncio.FIRST_COMPLETED)

            if q_task in done and eof_task not in done:
                eof_task.cancel()
                qe = q_task.result()
                asyncio.current_task().add_done_callback(lambda _: connection_queue.task_done(provider_id)) # type: ignore
            else:
                if q_task in done:
                    await connection_queue.put(provider_id, q_task.result())
                else:
                    q_task.cancel()
                eof_task.result()
                logger.info("Provider disconnected.")

                if q_task in done:
                    connection_queue.task_done(provider_id)

                return

            if qe.writer.is_closing():
                logger.warn("Probe disconnected early. Waiting for new request.")
                qe.writer.close()
                await qe.writer.wait_closed()
                continue
            else:
                break

        logger.debug(f"Received a connection request: {qe.con_req}")

        try:
            await write_msg(writer, qe.con_req)
        except Exception as e:
            logger.warn(f"Provider disconnected. {e}")
            await connection_queue.put(session_token.provider.id, qe)
            raise e

        logger.debug("Waiting for provider to accept connection request.")
        async with asyncio.timeout(config.PROVIDER_RESPONSE_TIMEOUT): # TODO: timeout status
            con_res = ConnectResponse.decode(await reader.readexactly(ConnectResponse.LENGTH))
        logger.debug(f"Received a response for a connection request: {con_res}")

        if con_res is None:
            logger.warn("Received malformed connection request status. Closing connections.")
            writer.close()
            await writer.wait_closed()
            qe.writer.close()
            await qe.writer.wait_closed()
            return

        logger.debug("Forwarding connection request status to probe.")
        await write_msg(qe.writer, con_res)

        if con_res.status != ConnectStatus.Success:
            logger.debug("Received unsuccessful connection status response. Closing connections.")
            writer.close()
            await writer.wait_closed()
            qe.writer.close()
            await qe.writer.wait_closed()
            return

        probe_stream = ApduStream(qe.sim, qe.reader, qe.writer)
        provider_stream = ApduStream(qe.sim, reader, writer)

        try:
            await self.handle_established_connection(probe_stream, provider_stream)
        finally:
            await provider_stream.close()
            await probe_stream.close()
