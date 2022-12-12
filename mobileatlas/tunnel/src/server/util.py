import asyncio
import logging

from typing import Optional
from tunnelTypes.connect import ConnectRequest, IdentifierType

logger = logging.getLogger(__name__)

async def write_msg(writer: asyncio.StreamWriter, msg):
    writer.write(msg.encode())
    await writer.drain()

def _con_req_missing(b: bytes) -> int:
    if len(b) < 2:
        return 10 - len(b)

    try:
        ident_type = IdentifierType(b[1])
        if ident_type == IdentifierType.Imsi:
            return 10 - len(b)
        elif ident_type == IdentifierType.Iccid:
            return 11 - len(b)
        else:
            raise NotImplemented
    except ValueError:
        return 0

async def read_con_req(reader: asyncio.StreamReader) -> Optional[ConnectRequest]:
    buf = await reader.read(n=11)

    if len(buf) == 0:
        raise EOFError

    missing = _con_req_missing(buf)
    while missing > 0:
        r = await reader.read(n=missing)

        if len(r) == 0:
            raise asyncio.IncompleteReadError(buf, missing)

        buf += r
        missing = _con_req_missing(buf)

    return ConnectRequest.decode(buf)

