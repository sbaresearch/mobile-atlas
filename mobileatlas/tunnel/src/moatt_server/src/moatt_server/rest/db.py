from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from .. import config

CONFIG = config.get_config()

_ENGINE = None
_SESSION_MAKER = None


def create_sessionmaker():
    global _ENGINE, _SESSION_MAKER

    if _ENGINE is None:
        _ENGINE = create_async_engine(CONFIG.db_url())
        _SESSION_MAKER = async_sessionmaker(_ENGINE)


async def dispose_engine():
    global _ENGINE, _SESSION_MAKER

    if _SESSION_MAKER is not None:
        _SESSION_MAKER = None

    if _ENGINE is not None:
        await _ENGINE.dispose()


async def get_db():
    assert (
        _SESSION_MAKER is not None
    ), "DB session was requested before the setup was completed."

    async with _SESSION_MAKER() as session:
        yield session
