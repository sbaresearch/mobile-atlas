import logging
import socket
import ssl
from typing import Optional

from moatt_clients.client import Client, ProtocolError
from moatt_clients.errors import SimRequestError
from moatt_clients.streams import ApduStream, RawStream
from moatt_types.connect import (
    ConnectionRequestFlags,
    ConnectRequest,
    ConnectResponse,
    ConnectStatus,
    Iccid,
    Imsi,
    SessionToken,
)

logger = logging.getLogger(__name__)


class ProbeClient(Client):
    """Client able to establish connections with SIM providers."""

    def __init__(
        self,
        session_token: SessionToken,
        host: str,
        port: str | int,
        tls_ctx: Optional[ssl.SSLContext] = None,
        server_hostname: Optional[str] = None,
        no_wait: bool = False,
    ):
        """

        Parameters
        ----------
        session_token
            Session token to use for this connection.
        host
            Server host.
        port
            Server port.
        tls_ctx
            Optional TLS configuration.
        server_hostname
            TLS server hostname.
        """
        super().__init__(
            session_token, host, port, tls_ctx=tls_ctx, server_hostname=server_hostname
        )
        self.no_wait = no_wait

    def connect(self, sim_id: Imsi | Iccid) -> Optional[ApduStream]:
        """Establish a connection with a SIM provider.

        Parameters
        ----------
        sim_id
            The SIM card to request the connection for.
        """
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
            raise

        if apdu_stream is None:
            stream.close()

        return apdu_stream

    def _connect(self, stream: RawStream, sim_id: Imsi | Iccid) -> Optional[ApduStream]:
        self._authenticate(stream)

        logger.debug(f"Sending connection request ({sim_id})")

        flags = ConnectionRequestFlags.DEFAULT
        if self.no_wait:
            flags |= ConnectionRequestFlags.NO_WAIT

        stream.write_all(ConnectRequest(sim_id, flags=flags).encode())

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
