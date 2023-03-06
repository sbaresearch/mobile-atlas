import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession

from moatt_server.tunnel.probe_handler import ProbeHandler
from moatt_server.tunnel.provider_handler import ProviderHandler

logger = logging.getLogger(__name__)

def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    url = "sqlite+aiosqlite:///app.db"

    engine = create_async_engine(url)
    return async_sessionmaker(engine) # expire_on_commit=False

async def main():
    logging.basicConfig(level=logging.DEBUG)

    async_session = get_async_session_factory()

    probe_handler = ProbeHandler(async_session)
    provider_handler = ProviderHandler(async_session)
    probe_server = await asyncio.start_server(probe_handler.handle, ['0.0.0.0', '::'], 5555)
    provider_server = await asyncio.start_server(provider_handler.handle, ['0.0.0.0', '::'], 6666)
    logger.debug("Starting Server...")
    await asyncio.gather(
            probe_server.serve_forever(),
            provider_server.serve_forever()
        )

if __name__ == "__main__":
    asyncio.run(main())
