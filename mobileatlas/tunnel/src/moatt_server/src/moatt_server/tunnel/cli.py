import argparse
import asyncio
import logging
import socket
import ssl

import uvloop
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .. import config
from ..gc import gc
from .connection_queue import queue_gc_coro_factory
from .probe_handler import ProbeHandler
from .provider_handler import ProviderHandler

LOGGER = logging.getLogger(__name__)


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(config.get_config().db_url())
    return async_sessionmaker(engine, expire_on_commit=False)


async def start_server(cert, cert_key):
    tls_ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    tls_ctx.load_cert_chain(cert, cert_key)

    async_session = get_async_session_factory()

    probe_handler = ProbeHandler(async_session)
    provider_handler = ProviderHandler(async_session)
    probe_server = await asyncio.start_server(
        probe_handler.handle, ["0.0.0.0", "::"], 5555, ssl=tls_ctx
    )
    provider_server = await asyncio.start_server(
        provider_handler.handle, ["0.0.0.0", "::"], 6666, ssl=tls_ctx
    )

    for s in probe_server.sockets:
        set_keepalive_opts(s)
    for s in provider_server.sockets:
        set_keepalive_opts(s)

    LOGGER.debug("Starting Server...")
    async with asyncio.TaskGroup() as tg:
        tg.create_task(probe_server.serve_forever())
        tg.create_task(provider_server.serve_forever())
        tg.create_task(
            gc(
                [queue_gc_coro_factory(config.get_config().QUEUE_GC_INTERVAL)],
                config.get_config().GC_INTERVAL,
            )
        )


def set_keepalive_opts(sock: socket.socket):
    sock.setsockopt(
        socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, config.get_config().TCP_KEEPIDLE
    )
    sock.setsockopt(
        socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, config.get_config().TCP_KEEPINTVL
    )
    sock.setsockopt(
        socket.IPPROTO_TCP, socket.TCP_KEEPCNT, config.get_config().TCP_KEEPCNT
    )
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)


def main():
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()

    parser.add_argument("--cert", default="ssl/server.crt")
    parser.add_argument("--cert-key", default="ssl/server.key")
    parser.add_argument("--config", default="config.toml")
    args = parser.parse_args()

    config.init_config(args.config)
    uvloop.run(start_server(args.cert, args.cert_key))


if __name__ == "__main__":
    main()
