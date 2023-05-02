import argparse
import asyncio
import logging
import ssl

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from moatt_server.tunnel.probe_handler import ProbeHandler
from moatt_server.tunnel.provider_handler import ProviderHandler

logger = logging.getLogger(__name__)

def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    url = "sqlite+aiosqlite:///app.db"

    engine = create_async_engine(url)
    return async_sessionmaker(engine, expire_on_commit=False)

async def start_server(args):
    logging.basicConfig(level=logging.DEBUG)

    tls_ctx = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    tls_ctx.load_cert_chain(args.cacert, args.cakey)

    async_session = get_async_session_factory()

    probe_handler = ProbeHandler(async_session)
    provider_handler = ProviderHandler(async_session)
    probe_server = await asyncio.start_server(probe_handler.handle, ['0.0.0.0', '::'], 5555, ssl=tls_ctx)
    provider_server = await asyncio.start_server(provider_handler.handle, ['0.0.0.0', '::'], 6666, ssl=tls_ctx)
    logger.debug("Starting Server...")
    await asyncio.gather(
            probe_server.serve_forever(),
            provider_server.serve_forever()
        )

def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--cacert", default="./server.crt")
    parser.add_argument("--cakey", default="./server.key")
    args = parser.parse_args()

    asyncio.run(start_server(args))

if __name__ == "__main__":
    main()
