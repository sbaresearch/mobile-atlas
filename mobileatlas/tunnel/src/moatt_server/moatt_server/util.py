import asyncio
import logging

from typing import Optional
from moatt_types.connect import ConnectRequest, IdentifierType, Imsi, Iccid

logger = logging.getLogger(__name__)

async def write_msg(writer: asyncio.StreamWriter, msg):
    writer.write(msg.encode())
    await writer.drain()

def _con_req_missing(b: bytes) -> int:
    if len(b) < 2:
        return ConnectRequest.MIN_LENGTH - len(b)

    try:
        ident_type = IdentifierType(b[1])
        if ident_type == IdentifierType.Imsi:
            return (2 + Imsi.LENGTH) - len(b)
        elif ident_type == IdentifierType.Iccid:
            return (2 + Iccid.LENGTH) - len(b)
        else:
            logger.warn("NotImplemented")
            raise NotImplemented
    except ValueError as e:
        logger.warn(f"ValueError: {e}")
        return 0

async def read_con_req(reader: asyncio.StreamReader) -> Optional[ConnectRequest]:
    buf = await reader.read(n=ConnectRequest.MIN_LENGTH)

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

