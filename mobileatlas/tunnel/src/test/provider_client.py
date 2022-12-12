import asyncio
import logging

from util import read_con_req
from apdu_stream import ApduStream
from auth import read_tokens
from typing import Optional

from connect_types import (AuthRequest, AuthResponse, ConnectResponse, ConnectStatus,
                           ApduPacket, ApduOp, AuthStatus)

logger = logging.getLogger(__name__)
token = read_tokens()[0]

async def write(writer: asyncio.StreamWriter, msg):
    writer.write(msg.encode())
    await writer.drain()

class Client:
    def __init__(self, identifier, token, host, port):
        self.identifier = identifier
        self.token = token
        self.host = host
        self.port = port

    async def register(self) -> Optional[ApduStream]:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            stream = await self._register(reader, writer)
        except:
            writer.close()
            await writer.wait_closed()
            return

        if stream == None:
            writer.close()
            await writer.wait_closed()

        return stream

    async def _register(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> Optional[ApduStream]:
        await write(writer, AuthRequest(self.identifier, self.token))
        auth_res = AuthResponse.decode(await reader.readexactly(AuthResponse.LENGTH))
        logger.debug(f"{auth_res}")

        if auth_res == None:
            logger.warn("Malformed authorisation response.")
            return None

        if auth_res.status != AuthStatus.Success:
            logger.warn("Received malformed message during connection.")
            return None

        logging.debug("Waiting for connection...")

        conn_req = await read_con_req(reader)

        if conn_req == None:
            logger.warn("Malformed connection request.")
            return None

        logger.debug(f"Requested SIM: {conn_req.identifier}")

        await write(writer, ConnectResponse(ConnectStatus.Success))

        return ApduStream(self.token, reader, writer)

async def main():
    logging.basicConfig(level=logging.DEBUG)
    client = Client(1, token, "::1", 6666)
    stream = await client.register()

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
