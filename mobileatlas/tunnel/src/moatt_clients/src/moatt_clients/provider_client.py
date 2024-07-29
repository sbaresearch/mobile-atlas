import dataclasses
import logging
import socket
import ssl
from typing import Any, Callable, Optional

import requests
from moatt_types.connect import (
    AuthType,
    ConnectRequest,
    ConnectResponse,
    ConnectStatus,
    Iccid,
    Imsi,
    SimIdentifierType,
    Token,
)

from moatt_clients.client import ProtocolError, _Client
from moatt_clients.errors import SimRequestError
from moatt_clients.streams import ApduStream, RawStream

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class SIM:
    id: int
    iccid: Optional[Iccid] = None
    imsi: Optional[Imsi] = None

    def _to_dict(self) -> dict[str, Any]:
        r: dict[str, Any] = {"id": self.id}

        if self.iccid is not None:
            r["iccid"] = self.iccid.iccid

        if self.imsi is not None:
            r["imsi"] = self.imsi.imsi

        return r


def register_sims(
    api_url: str,
    session_token: Token,
    sims: list[SIM],
) -> None:
    """Register SIM cards with the tunnel server.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    session_token
        A valid session token.
    sims
        SIM cards to register.

    Raises
    ------
    requests.HTTPError
        If registration is not successful.
    """
    headers = {"Authorization": f"Bearer {session_token.as_base64()}"}
    r = requests.put(
        f"{api_url}/provider/sims",
        json=list(map(lambda s: s._to_dict(), sims)),
        headers=headers,
    )

    try:
        r.raise_for_status()
    except requests.HTTPError:
        LOGGER.error(
            "Registration failed. Received status %s from server.", r.status_code
        )
        raise


class ProviderClient(_Client):
    """
    Client used to provide SIM cards to the MobileAtlas tunnel server.
    """

    def __init__(
        self,
        session_token: Token,
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
            Tunnel-Server hostname
        port
            Port of the Tunnel-Server
        cb
            Callback deciding whether requested SIM card is available.
        tls_ctx
            Optional TLS configuration.
        server_hostname
            Optional TLS server hostname used in server certificate validation.
        """
        self.cb = cb
        super().__init__(
            session_token, host, port, tls_ctx=tls_ctx, server_hostname=server_hostname
        )

    def wait_for_connection(self) -> tuple[SimIdentifierType, ApduStream]:
        """Wait for a single connection request.

        Returns
        -------
        Identifier of the requested SIM card and connected ApduStream.
        """
        LOGGER.debug("Opening connection.")
        try:
            stream = RawStream(
                self.tls_ctx.wrap_socket(
                    socket.create_connection((self.host, self.port)),
                    server_hostname=self.server_hostname,
                )
            )
        except Exception as e:
            LOGGER.warning(f"Could not connect to server: {e}")
            raise ConnectionError from e

        try:
            apdu_stream = self._wait_for_connection(stream)
        except Exception as e:
            LOGGER.warning(f"Exception was raised while waiting for connection: {e}")
            stream.close()
            raise

        if apdu_stream is None:
            LOGGER.debug("APDU stream is none")
            stream.close()

        return apdu_stream

    def _wait_for_connection(
        self,
        stream: RawStream,
    ) -> tuple[SimIdentifierType, ApduStream]:
        self._authenticate(AuthType.Provider, stream)

        logging.debug("Waiting for connection request.")
        conn_req = stream.read_message(ConnectRequest.decode)

        if conn_req is None:
            LOGGER.warning("Malformed connection request.")
            raise ProtocolError

        LOGGER.debug(f"Received request for SIM: {conn_req.identifier}")

        status = self.cb(conn_req)

        LOGGER.debug(f"Sending connection response with status: {status}")
        stream.write_all(ConnectResponse(status).encode())

        if status != ConnectStatus.Success:
            LOGGER.info(
                f"Rejected request for SIM '{conn_req.identifier}' with '{status}'"
            )
            raise SimRequestError(status, conn_req.identifier)

        return (conn_req.identifier, ApduStream(stream))
