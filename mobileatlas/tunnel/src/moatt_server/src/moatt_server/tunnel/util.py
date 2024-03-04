import asyncio
import logging
from typing import Callable, TypeVar

from moatt_types.connect import PartialInput

LOGGER = logging.getLogger(__name__)


async def write_msg(writer: asyncio.StreamWriter, msg) -> None:
    writer.write(msg.encode())
    await writer.drain()


T = TypeVar("T")


async def read_msg(reader: asyncio.StreamReader, parser: Callable[[bytes], T]) -> T:
    buf = b""

    while True:
        try:
            return parser(buf)
        except PartialInput as e:
            r = await reader.read(n=e.bytes_missing)

            if len(r) == 0:
                raise asyncio.IncompleteReadError(buf, e.bytes_missing)

            buf += r


async def poll_eof(writer: asyncio.StreamWriter, interval=10) -> None:
    while True:
        if writer.is_closing():
            return
        await asyncio.sleep(interval)
