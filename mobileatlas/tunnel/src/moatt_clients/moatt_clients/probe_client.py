import logging
import socket
import ssl

from typing import Optional, Union

from moatt_clients.client import Client
from moatt_clients.streams import TcpStream, ApduStream
from moatt_types.connect import (AuthStatus, ConnectRequest, ConnectResponse, Imsi, Iccid,
                             ConnectStatus, SessionToken)

logger = logging.getLogger(__name__)

class ProbeClient(Client):
    def __init__(
            self,
            session_token: SessionToken,
            host,
            port,
            tls_ctx: Optional[ssl.SSLContext] = None,
            server_hostname = None,
            ):
        super().__init__(
                session_token,
                host,
                port,
                tls_ctx=tls_ctx,
                server_hostname=server_hostname
                )

    def connect(self, sim_id) -> Optional[ApduStream]:
        logger.debug("Opening connection.")

        stream = TcpStream(
                self.tls_ctx.wrap_socket(
                    socket.create_connection((self.host, self.port)),
                    server_hostname=self.server_hostname,
                    )
                )

        try:
            apdu_stream = self._connect(stream, sim_id)
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            stream.close()
            return None

        if apdu_stream is None:
            stream.close()

        return apdu_stream

    def _connect(self, stream: TcpStream, sim_id: Union[Imsi, Iccid]) -> Optional[ApduStream]:
        auth_status = self._authenticate(stream)

        if auth_status != AuthStatus.Success:
            logger.info("Authorisation failed!")
            return None

        logger.debug(f"Sending connection request ({sim_id})")
        stream.write_all(ConnectRequest(sim_id).encode())

        logger.debug("Waiting for answer to connection request message.")
        conn_res = ConnectResponse.decode(stream.read_exactly(ConnectResponse.LENGTH))

        if conn_res is None:
            logger.warn("Received malformed message during connection.")
            return None

        if conn_res.status != ConnectStatus.Success:
            logger.info(f"Requesting SIM {sim_id} failed!")
            return None

        return ApduStream(stream)
