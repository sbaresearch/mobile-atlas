import argparse
import asyncio
import logging
import ssl
import socket

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from moatt_server.tunnel.probe_handler import ProbeHandler
from moatt_server.tunnel.provider_handler import ProviderHandler
from moatt_server.gc import gc
from moatt_server.tunnel.connection_queue import queue_gc_coro_factory
import moatt_server.config as config

logger = logging.getLogger(__name__)

def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    url = "sqlite+aiosqlite:///app.db"

    engine = create_async_engine(url)
    return async_sessionmaker(engine, expire_on_commit=False)

async def start_server(args):
    logging.basicConfig(level=logging.DEBUG)

    tls_ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    tls_ctx.load_cert_chain(args.cert, args.cert_key)

    async_session = get_async_session_factory()

    probe_handler = ProbeHandler(async_session)
    provider_handler = ProviderHandler(async_session)
    probe_server = await asyncio.start_server(probe_handler.handle, ['0.0.0.0', '::'], 5555, ssl=tls_ctx)
    provider_server = await asyncio.start_server(provider_handler.handle, ['0.0.0.0', '::'], 6666, ssl=tls_ctx)

    for s in probe_server.sockets:
        set_keepalive_opts(s)
    for s in provider_server.sockets:
        set_keepalive_opts(s)

    logger.debug("Starting Server...")
    async with asyncio.TaskGroup() as tg:
        tg.create_task(probe_server.serve_forever())
        tg.create_task(provider_server.serve_forever())
        tg.create_task(gc([queue_gc_coro_factory(config.QUEUE_GC_INTERVAL)], config.GC_INTERVAL))

def set_keepalive_opts(sock):
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, config.TCP_KEEPIDLE)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, config.TCP_KEEPINTVL)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, config.TCP_KEEPCNT)

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--cert", default="ssl/server.crt")
    parser.add_argument("--cert-key", default="ssl/server.key")
    args = parser.parse_args()

    asyncio.run(start_server(args))

if __name__ == "__main__":
    main()
