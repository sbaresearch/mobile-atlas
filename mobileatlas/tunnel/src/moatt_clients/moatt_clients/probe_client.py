import logging
import socket
import ssl
import time

from typing import Optional, Union

from moatt_clients.client import Client, ProtocolError
from moatt_clients.errors import SimRequestError
from moatt_clients.streams import RawStream, ApduStream
from moatt_types.connect import (ConnectRequest, ConnectResponse, Imsi, Iccid,
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

        stream = RawStream(
                self.tls_ctx.wrap_socket(
                    socket.create_connection((self.host, self.port)),
                    server_hostname=self.server_hostname,
                    )
                )

        try:
            apdu_stream = self._connect(stream, sim_id)
        except Exception as e:
            logger.error(f"Connection failed ({fmt_error(e)}). Closing connection.")
            stream.close()
            raise e

        if apdu_stream is None:
            stream.close()

        return apdu_stream

    def _connect(self, stream: RawStream, sim_id: Union[Imsi, Iccid]) -> Optional[ApduStream]:
        self._authenticate(stream)

        logger.debug(f"Sending connection request ({sim_id})")
        stream.write_all(ConnectRequest(sim_id).encode())

        logger.debug("Waiting for answer to connection request message.")
        conn_res = ConnectResponse.decode(stream.read_exactly(ConnectResponse.LENGTH))

        if conn_res is None:
            logger.warn("Received malformed message during connection.")
            raise ProtocolError("Received a malformed message while trying to connect.")

        if conn_res.status != ConnectStatus.Success:
            logger.info(f"Requesting SIM {sim_id} failed!")
            raise SimRequestError(conn_res.status, sim_id)

        return ApduStream(stream)

def fmt_error(e) -> str:
    s = str(e)

    if len(s) != 0:
        s = ": " + s

    return f"{type(e).__name__}" + s
