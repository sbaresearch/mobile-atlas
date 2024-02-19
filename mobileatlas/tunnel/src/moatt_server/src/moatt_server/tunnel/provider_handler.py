import asyncio
import logging

from moatt_types.connect import (
    AuthResponse,
    AuthStatus,
    ConnectResponse,
    ConnectStatus,
    Iccid,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .. import auth, config, db
from .. import models as dbm
from . import connection_queue
from .apdu_stream import ApduStream
from .handler import Handler
from .util import poll_eof, write_msg

LOGGER = logging.getLogger(__name__)


class ProviderHandler(Handler):
    def __init__(self, async_session: async_sessionmaker[AsyncSession], timeout=0):
        super().__init__(async_session, timeout)

    async def handle_established_connection(
        self, probe: ApduStream, provider: ApduStream
    ):
        probe_task = asyncio.create_task(probe.recv(), name="probe")
        provider_task = asyncio.create_task(provider.recv(), name="provider")

        try:
            while True:
                done, pending = await asyncio.wait(
                    [probe_task, provider_task], return_when=asyncio.FIRST_COMPLETED
                )

                assert len(done) > 0 and len(done) <= 2
                assert len(pending) >= 0 and len(pending) < 2
                for t in done:
                    try:
                        r = t.result()
                    except asyncio.IncompleteReadError as e:
                        LOGGER.warn(
                            f"Unexpected EOF while trying to read from {t.get_name()} "
                            f"connection. (expected at least {e.expected} more bytes.)"
                        )

                        return
                    except ValueError:
                        LOGGER.warn("Received a malformed packet. Closing connections.")
                        return

                    if r is None:
                        LOGGER.info(f"{t.get_name()} closed the connection.")
                        return

                    async with self.async_session() as session, session.begin():
                        await auth.log_apdu(
                            session,
                            probe.sim.iccid,
                            r,
                            (
                                dbm.Sender.Probe
                                if t.get_name() == "probe"
                                else dbm.Sender.Provider
                            ),
                        )

                    if t.get_name() == "probe":
                        provider.send_background(r)
                        probe_task = asyncio.create_task(probe.recv(), name="probe")
                    elif t.get_name() == "provider":
                        probe.send_background(r)
                        provider_task = asyncio.create_task(
                            provider.recv(), name="provider"
                        )
        finally:
            probe_task.cancel()
            provider_task.cancel()
            await probe.close()
            await provider.close()

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            await self._handle(reader, writer)
        except (EOFError, ConnectionResetError):
            LOGGER.warn("Client closed connection unexpectedly.")
        except asyncio.QueueFull as e:
            LOGGER.warn(
                "Failed to requeue connection request because either the queue"
                "was full or because the client did not want to wait."
            )
            probe_writer = e.args[0].writer
            await write_msg(
                probe_writer, ConnectResponse(ConnectStatus.ProviderTimedOut)
            )
            probe_writer.close()
            await probe_writer.wait_closed()
        except Exception as e:
            LOGGER.warn(f"Exception occurred while handling connection: {e}")
        finally:
            if not writer.is_closing():
                writer.close()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        session_token = await self._handle_auth_req(reader, writer)

        assert session_token is not None

        if session_token.provider is None:
            LOGGER.debug("Session token was not used to register a provider.")
            await write_msg(writer, AuthResponse(AuthStatus.ProviderNotRegistered))
            writer.close()
            await writer.wait_closed()
            return

        await write_msg(writer, AuthResponse(AuthStatus.Success))

        provider_id = session_token.provider.id

        async with self.async_session() as session, session.begin():
            await db.provider_available(session, provider_id)

        try:
            while True:
                LOGGER.debug("waiting for connection request.")
                q_task = asyncio.create_task(
                    connection_queue.get(provider_id), name="q"
                )

                # poll whether the provider is still connected
                # in order to prevent a buildup of tasks that
                # cannot make progress but wait on a connection request to arrive regardless
                eof_task = asyncio.create_task(poll_eof(writer), name="eof")

                done, _ = await asyncio.wait(
                    [q_task, eof_task], return_when=asyncio.FIRST_COMPLETED
                )

                if q_task in done and eof_task not in done:
                    eof_task.cancel()
                    qe = q_task.result()
                    asyncio.current_task().add_done_callback(  # pyright: ignore[reportOptionalMemberAccess]
                        lambda _: connection_queue.task_done(provider_id)
                    )
                else:
                    if q_task in done:
                        connection_queue.put_nowait(provider_id, q_task.result())
                    else:
                        q_task.cancel()
                    eof_task.result()
                    LOGGER.info("Provider disconnected.")

                    if q_task in done:
                        connection_queue.task_done(provider_id)

                    return

                if qe.writer.is_closing():
                    LOGGER.warn("Probe disconnected early. Waiting for new request.")
                    qe.writer.close()
                    await qe.writer.wait_closed()
                    continue
                else:
                    break
        finally:
            async with self.async_session() as session, session.begin():
                await db.provider_unavailable(session, provider_id)

        LOGGER.debug(f"Received a connection request: {qe.con_req}")

        try:
            await write_msg(writer, qe.con_req)
        except Exception as e:
            LOGGER.warn(f"Provider disconnected. {e}")
            connection_queue.put_nowait(session_token.provider.id, qe)
            raise

        LOGGER.debug("Waiting for provider to accept connection request.")
        try:
            async with asyncio.timeout(config.get_config().PROVIDER_RESPONSE_TIMEOUT):
                con_res = ConnectResponse.decode(
                    await reader.readexactly(ConnectResponse.LENGTH)
                )
        except TimeoutError:
            LOGGER.info("Provider timed out.")
            await write_msg(qe.writer, ConnectResponse(ConnectStatus.ProviderTimedOut))
            qe.writer.close()
            await qe.writer.wait_closed()
            return
        LOGGER.debug(f"Received a response for a connection request: {con_res}")

        if con_res is None:
            LOGGER.warn(
                "Received malformed connection request status. Closing connections."
            )
            writer.close()
            await writer.wait_closed()
            qe.writer.close()
            await qe.writer.wait_closed()
            return

        LOGGER.debug("Forwarding connection request status to probe.")
        await write_msg(qe.writer, con_res)

        if con_res.status != ConnectStatus.Success:
            LOGGER.debug(
                "Received unsuccessful connection status response. Closing connections."
            )
            writer.close()
            await writer.wait_closed()
            qe.writer.close()
            await qe.writer.wait_closed()
            return

        iccid = Iccid(qe.sim.iccid)
        probe_stream = None
        provider_stream = None
        try:
            probe_stream = ApduStream(qe.sim, qe.reader, qe.writer)
            provider_stream = ApduStream(qe.sim, reader, writer)

            async with self.async_session() as session, session.begin():
                await db.sim_used(session, session_token, iccid)

            await self.handle_established_connection(probe_stream, provider_stream)
        finally:
            if provider_stream is not None:
                await provider_stream.close()
            if probe_stream is not None:
                await probe_stream.close()

            async with self.async_session() as session, session.begin():
                await db.sim_unused(session, session_token, iccid)
