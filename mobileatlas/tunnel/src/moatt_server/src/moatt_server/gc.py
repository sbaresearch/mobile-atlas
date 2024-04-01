import asyncio
import logging
import traceback
from collections.abc import Awaitable, Callable
from datetime import timedelta

logger = logging.getLogger(__name__)


async def gc(coros: list[Callable[[], Awaitable[None]]], interval: timedelta):
    while True:
        await asyncio.sleep(interval.total_seconds())
        try:
            logger.info("Starting GC tasks")
            res = await asyncio.gather(
                *map(lambda x: x(), coros), return_exceptions=True
            )
            logger.info("GC tasks finished")
            for e in filter(lambda r: isinstance(r, Exception), res):
                logger.warn(f"GC task failed with: {e}")
                traceback.print_exception(e)
        except Exception as e:
            logger.warn(f"Error while running gc task: {e}")
