from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from .. import config

_ENGINE = None


def create_sessionmaker():
    global _ENGINE, _SESSION_MAKER

    if _ENGINE is None:
        _ENGINE = create_async_engine(config.get_config().db_url())


async def dispose_engine():
    global _ENGINE, _SESSION_MAKER

    if _ENGINE is not None:
        await _ENGINE.dispose()


async def get_db():
    assert (
        _ENGINE is not None
    ), "DB session was requested before the setup was completed."

    async with AsyncSession(_ENGINE, autobegin=False) as session:
        yield session
