import asyncio
import logging
import sys

from auth import read_tokens, Token
from connect_types import (AuthRequest, AuthResponse, AuthStatus, Imsi, Iccid, ConnectRequest,
                           ConnectResponse, ConnectStatus, ApduPacket, ApduOp)
from apdu_stream import ApduStream
from typing import Optional

logger = logging.getLogger(__name__)

token = read_tokens()[0]

class Client:
    def __init__(self, identifier: int, token: Token, host, port):
        self.identifier = identifier
        self.token = token
        self.host = host
        self.port = port

    async def connect(self, sim_id: Imsi | Iccid) -> Optional[ApduStream]:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            stream = await self._connect(sim_id, reader, writer)
        except:
            writer.close()
            await writer.wait_closed()
            return

        if stream == None:
            writer.close()
            await writer.wait_closed()

        return stream

    async def _connect(self, sim_id: Imsi | Iccid,
                       reader: asyncio.StreamReader,
                       writer: asyncio.StreamWriter) -> Optional[ApduStream]:
        await write(writer, AuthRequest(self.identifier, self.token))
        logger.debug("Waiting for authorisation status message.")
        auth_res = AuthResponse.decode(await reader.readexactly(AuthResponse.LENGTH))

        if auth_res == None:
            logger.warn("Received malformed message during connection.")
            return None

        if auth_res.status != AuthStatus.Success:
            logger.info("Authorisation failed!")
            return None

        await write(writer, ConnectRequest(sim_id))

        logger.debug("Waiting for answer to connection request message.")
        conn_res = ConnectResponse.decode(await reader.readexactly(ConnectResponse.LENGTH))

        if conn_res == None:
            logger.warn("Received malformed message during connection.")
            return None

        if conn_res.status != ConnectStatus.Success:
            logger.info(f"Requesting SIM {sim_id} failed!")
            return None

        return ApduStream(self.token, reader, writer)

async def write(writer: asyncio.StreamWriter, msg):
    writer.write(msg.encode())
    await writer.drain()

async def main():
    client = Client(2, token, "::1", 5555)
    logger.debug("Trying to connect.")
    stream = await client.connect(Imsi(b"\x01\x02\x03\x04\x05\x06\x07\x08"))

    if stream == None:
        raise Exception("Connection failed")

    logger.debug("Connected")

    input_task = asyncio.create_task(asyncio.to_thread(lambda: input("msg> ")), name="input")
    recv_task = asyncio.create_task(stream.recv(), name="recv")

    while True:
        done, _ = await asyncio.wait([input_task, recv_task], return_when=asyncio.FIRST_COMPLETED)

        for t in done:
            if t.get_name() == "input":
                r = t.result()
                if r != None:
                    stream.send_background(ApduPacket(ApduOp.Apdu, r.encode()))
                input_task = asyncio.create_task(asyncio.to_thread(lambda: input("msg> ")), name="input")
            elif t.get_name() == "recv":
                apdu = t.result()

                if apdu == None:
                    print("Received EOF.")
                    return

                print(apdu)
                recv_task = asyncio.create_task(stream.recv(), name="recv")

if __name__ == "__main__":
    asyncio.run(main())
