import asyncio
import logging
import socket
import ssl
from collections.abc import Sequence
from datetime import timedelta
from typing import Generic, TypeVar

from moatt_types.connect import (
    AuthRequest,
    AuthResponse,
    AuthStatus,
    AuthType,
    ConnectResponse,
    ConnectStatus,
    Token,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .. import auth
from ..auth import TokenError
from ..auth_handler import AuthHandler
from ..config import Config
from ..gc import gc
from .connection_queue import queue_gc_coro_factory
from .probe_handler import ProbeHandler
from .provider_handler import ProviderHandler
from .util import read_msg, write_msg

LOGGER = logging.getLogger(__name__)

H = TypeVar("H", bound=AuthHandler)


class Server(Generic[H]):
    def __init__(
        self,
        config: Config,
        host: str | Sequence[str] = "localhost",
        port: int | str | None = None,
        tls_ctx: ssl.SSLContext | None = None,
        *,
        limit: int = 64 * 2**10,
        **kwargs,
    ):
        self._config = config

        if tls_ctx is None:
            LOGGER.warning(
                "No TLS context configured. Server will be using plain TCP sockets."
            )

        self._tls_ctx = tls_ctx
        self._host = host
        self._port = port
        self._limit = limit
        self._kwargs = kwargs
        self._server = None

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        LOGGER.debug("Handling new connection...")
        close = False
        try:
            await self._dispatch(reader, writer)
        except (EOFError, ConnectionResetError):
            LOGGER.warn("Client closed connection unexpectedly.")
            close = True
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
            close = True
        except Exception as e:
            LOGGER.exception("Exception occurred while handling connection.")
            close = True

        if close:
            if not writer.is_closing():
                writer.close()

    async def _dispatch(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        LOGGER.debug("Waiting for authorisation message.")
        async with asyncio.timeout(
            self._config.AUTHMSG_TIMEOUT.total_seconds()
            if self._config.AUTHMSG_TIMEOUT
            else None
        ):
            auth_req = await read_msg(reader, AuthRequest.decode)
        LOGGER.debug("Received authorisation message: %s", auth_req)

        if auth_req is None:
            LOGGER.warn("Received malformed authorisation message. Closing connection.")
            writer.close()
            await writer.wait_closed()
            return None

        try:
            await self._valid_token(auth_req.auth_type, auth_req.session_token)
        except TokenError as e:
            LOGGER.debug(
                f"Received an invalid session token. Closing connection. (Reason: %s)",
                e.etype,
            )
            await write_msg(writer, AuthResponse(e.to_auth_status()))
            writer.close()
            await writer.wait_closed()
            return None

        LOGGER.debug("Sending successful authorisation message.")
        await write_msg(writer, AuthResponse(AuthStatus.Success))

        match auth_req.auth_type:
            case AuthType.Provider:
                await self._provider_handler.handle(
                    reader, writer, auth_req.session_token
                )
            case AuthType.Probe:
                await self._probe_handler.handle(reader, writer, auth_req.session_token)
            case _:
                raise NotImplementedError

    async def _valid_token(self, auth_type: AuthType, token: Token) -> None:
        match auth_type:
            case AuthType.Provider:
                async with self._sessionmaker() as session, session.begin():
                    await auth.provider_registered(session, token)
            case AuthType.Probe:
                await auth.register_probe(token)
            case _:
                raise NotImplementedError

    async def start(self):
        if self._server is not None:
            raise AssertionError("Server is already running.")

        self._sessionmaker = await self._create_session_factory()
        self._probe_handler = ProbeHandler(self._config, self._sessionmaker)
        self._provider_handler = ProviderHandler(self._config, self._sessionmaker)

        LOGGER.debug(
            "Creating asyncio server. (Host: %s; Port: %d)", self._host, self._port
        )
        self._server = await asyncio.start_server(
            self._handle,
            self._host,
            self._port,
            limit=self._limit,
            ssl=self._tls_ctx,
            **self._kwargs,
        )

        LOGGER.debug("Setting socket keepalive options.")
        for s in self._server.sockets:
            self._set_keepalive_opts(s)

        LOGGER.info("Starting tunnel server...")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._server.serve_forever())
            if self._config.MAX_PROBE_WAITTIME is not None:
                tg.create_task(
                    gc(
                        [queue_gc_coro_factory(self._config.MAX_PROBE_WAITTIME)],
                        self._config.GC_INTERVAL,
                    )
                )

    async def _create_session_factory(self) -> async_sessionmaker[AsyncSession]:
        engine = create_async_engine(self._config.db_url())

        while True:
            try:
                async with engine.begin() as conn:
                    from .. import models as dbm

                    await conn.run_sync(dbm.Base.metadata.create_all)
                break
            except Exception as e:
                LOGGER.exception(f"Failed to connect to database.\nRetrying in 10s...")
                await asyncio.sleep(10)

        return async_sessionmaker(engine, expire_on_commit=False)

    def _set_keepalive_opts(self, sock: socket.socket) -> None:
        if not self._config.TCP_KEEPALIVE:
            return

        if self._config.TCP_KEEPIDLE is not None:
            sock.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_KEEPIDLE,
                self._config.TCP_KEEPIDLE // timedelta(seconds=1),
            )

        if self._config.TCP_KEEPINTVL is not None:
            sock.setsockopt(
                socket.IPPROTO_TCP,
                socket.TCP_KEEPINTVL,
                self._config.TCP_KEEPINTVL // timedelta(seconds=1),
            )

        if self._config.TCP_KEEPCNT is not None:
            sock.setsockopt(
                socket.IPPROTO_TCP, socket.TCP_KEEPCNT, self._config.TCP_KEEPCNT
            )

        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
