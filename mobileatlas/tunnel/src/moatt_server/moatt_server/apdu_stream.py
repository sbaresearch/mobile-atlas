import asyncio
import logging
import struct

from typing import Optional
from moatt_types.connect import ApduPacket, Token

logger = logging.getLogger(__name__)

class ApduStream:
    def __init__(self, token: Token, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.token = token
        self.reader = reader
        self.writer = writer
        self.background_tasks = set()

    async def recv(self) -> Optional[ApduPacket]:
        buf = await self.reader.read(n=6)

        if len(buf) == 0:
            return None
            #raise EOFError
            #raise asyncio.IncompleteReadError(buf, self._bytes_missing(buf))

        missing = ApduStream._bytes_missing(buf)
        while missing > 0:
            r = await self.reader.read(n=missing)

            if len(r) == 0:
                raise asyncio.IncompleteReadError(buf, missing)

            buf += r
            missing = ApduStream._bytes_missing(buf)

        p = ApduPacket.decode(buf)

        if p == None:
            raise ValueError

        return p

    async def send(self, apdu: ApduPacket):
        self.writer.write(apdu.encode())
        await self.writer.drain()

    def send_background(self, apdu: ApduPacket):
        send_task = asyncio.create_task(self.send(apdu))
        self.background_tasks.add(send_task)
        # Callback is also invoked when the task is already done
        send_task.add_done_callback(self.background_tasks.discard)

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()

    @staticmethod
    def _bytes_missing(msg: bytes) -> int:
        if len(msg) < 6:
            return 6 - len(msg)

        l, = struct.unpack("!I", msg[2:6])
        if len(msg) < 6 + l:
            return (6 + l) - len(msg)
        else:
            return 0
