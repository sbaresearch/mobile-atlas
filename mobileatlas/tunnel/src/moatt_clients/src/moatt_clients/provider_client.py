import dataclasses
import logging
import socket
import ssl
from typing import Callable, Optional

import requests

from moatt_clients.client import Client, ProtocolError
from moatt_clients.errors import SimRequestError
from moatt_clients.streams import ApduStream, RawStream
from moatt_types.connect import (
    ConnectRequest,
    ConnectResponse,
    ConnectStatus,
    Iccid,
    IdentifierType,
    Imsi,
    SessionToken,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SIM:
    iccid: Iccid
    imsi: Imsi

    def _to_dict(self):
        return {"iccid": self.iccid.iccid, "imsi": self.imsi.imsi}


def register_sims(
    api_url: str,
    session_token: SessionToken,
    sims: list[SIM],
) -> Optional[SessionToken]:
    """Register SIM cards with the tunnel server.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    session_token
        The session to use.
    sims
        SIM cards to register.

    Raises
    ------
    requests.HTTPError
        If registration is not successful.
    """
    cookies = dict(session_token=session_token.as_base64())
    r = requests.put(
        f"{api_url}/provider/sims",
        json=list(map(lambda s: s._to_dict(), sims)),
        cookies=cookies,
    )

    try:
        r.raise_for_status()
    except requests.HTTPError:
        logger.error(
            f"Registration failed. Received {r.status_code} status from server."
        )
        raise


class ProviderClient(Client):
    def __init__(
        self,
        session_token: SessionToken,
        host: str,
        port: int,
        cb: Callable[[ConnectRequest], ConnectStatus],
        tls_ctx: Optional[ssl.SSLContext] = None,
        server_hostname=None,
    ):
        """
        Parameters
        ----------
        session_token
            Session token to use
        host
            Server hostname
        port
            Port of the provider tunnel service.
        cb
            Callback deciding whether requested SIM card is available.
        tls_ctx
            Optional TLS configuration to use.
        server_hostname
            TLS server hostname.
        """
        self.cb = cb
        super().__init__(
            session_token, host, port, tls_ctx=tls_ctx, server_hostname=server_hostname
        )

    def wait_for_connection(self) -> Optional[tuple[Imsi | Iccid, ApduStream]]:
        """Wait for a probe to request a connection.

        Returns
        -------
        ICCID or IMSI of the requested SIM card and apdu stream to be used.
        """
        logger.debug("Opening connection.")
        stream = RawStream(
            self.tls_ctx.wrap_socket(
                socket.create_connection((self.host, self.port)),
                server_hostname=self.server_hostname,
            )
        )

        try:
            apdu_stream = self._wait_for_connection(stream)
        except Exception as e:
            logger.warn(f"Exception was raised while waiting for connection: {e}")
            stream.close()
            return None

        if apdu_stream is None:
            logger.debug("APDU stream is none")
            stream.close()

        return apdu_stream

    def _wait_for_connection(
        self,
        stream: RawStream,
    ) -> Optional[tuple[Imsi | Iccid, ApduStream]]:
        self._authenticate(stream)

        logging.debug("Waiting for connection request.")
        conn_req = self._read_con_req(stream)

        if conn_req is None:
            logger.warn("Malformed connection request.")
            raise ProtocolError

        logger.debug(f"Received request for SIM: {conn_req.identifier}")

        status = self.cb(conn_req)

        logger.debug(f"Sending connection response with status: {status}")
        stream.write_all(ConnectResponse(status).encode())

        if status != ConnectStatus.Success:
            logger.info(
                f"Rejected request for SIM '{conn_req.identifier}' with '{status}'"
            )
            raise SimRequestError(status, conn_req.identifier)

        return (conn_req.identifier, ApduStream(stream))

    @staticmethod
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
                raise NotImplementedError
        except ProtocolError:
            return 0

    def _read_con_req(self, stream) -> Optional[ConnectRequest]:
        buf = stream.read(n=ConnectRequest.MIN_LENGTH)

        if len(buf) == 0:
            raise EOFError

        missing = ProviderClient._con_req_missing(buf)
        while missing > 0:
            r = stream.read(n=missing)

            if len(r) == 0:
                raise EOFError

            buf += r
            missing = ProviderClient._con_req_missing(buf)

        return ConnectRequest.decode(buf)
