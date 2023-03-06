import logging
import socket

from typing import Optional

from moatt_clients.client import Client
from moatt_clients.streams import TcpStream, ApduStream
from moatt_types.connect import (AuthStatus, ConnectRequest, ConnectResponse, Imsi, Iccid,
                             ConnectStatus, Token, SessionToken)

logger = logging.getLogger(__name__)

class ProbeClient(Client):
    def __init__(self, session_token: SessionToken, token: Token, host, port):
        super().__init__(session_token, token, host, port)

    def connect(self, sim_id) -> Optional[ApduStream]:
        logger.debug("Opening connection.")
        stream = TcpStream(socket.create_connection((self.host, self.port)))

        try:
            apdu_stream = self._connect(stream, sim_id)
        except:
            stream.close()
            return None

        if apdu_stream == None:
            stream.close()

        return apdu_stream

    def _connect(self, stream: TcpStream, sim_id: Imsi | Iccid) -> Optional[ApduStream]:
        auth_status = self._authenticate(stream)
        print(f"\n\nSTATUS {auth_status}")

        if auth_status != AuthStatus.Success:
            logger.info("Authorisation failed!")
            return None

        logger.debug(f"Sending connection request ({sim_id})")
        stream.write_all(ConnectRequest(sim_id).encode())

        logger.debug("Waiting for answer to connection request message.")
        conn_res = ConnectResponse.decode(stream.read_exactly(ConnectResponse.LENGTH))

        if conn_res == None:
            logger.warn("Received malformed message during connection.")
            return None

        if conn_res.status != ConnectStatus.Success:
            logger.info(f"Requesting SIM {sim_id} failed!")
            return None

        return ApduStream(stream)
