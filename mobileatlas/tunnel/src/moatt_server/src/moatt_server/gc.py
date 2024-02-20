import asyncio
import logging

logger = logging.getLogger(__name__)


async def gc(coros, interval):
    while True:
        await asyncio.sleep(interval)
        try:
            logger.info("Starting GC tasks")
            res = await asyncio.gather(
                *map(lambda x: x(), coros), return_exceptions=True
            )
            logger.info("GC tasks finished")
            for e in filter(lambda r: isinstance(r, Exception), res):
                logger.warn(f"GC task failed with: {e}")
        except Exception as e:
            logger.warn(f"Error while running gc task: {e}")
