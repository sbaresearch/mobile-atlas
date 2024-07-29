import logging
import ssl
from typing import Optional

from moatt_types.connect import AuthRequest, AuthResponse, AuthStatus, AuthType, Token

from moatt_clients.errors import AuthError, ProtocolError
from moatt_clients.streams import RawStream

LOGGER = logging.getLogger(__name__)


class _Client:
    """
    Base class for the Provider- and ProbeClient classes.
    Should not be used directly.
    """

    def __init__(
        self,
        session_token: Token,
        host,
        port,
        tls_ctx: Optional[ssl.SSLContext] = None,
        server_hostname=None,
    ):
        self.session_token = session_token
        self.host = host
        self.port = port
        self.tls_ctx = tls_ctx if tls_ctx is not None else ssl.create_default_context()
        self.server_hostname = server_hostname if server_hostname is not None else host

    def _authenticate(self, auth_type: AuthType, stream: RawStream) -> None:
        LOGGER.debug("Sending authorisation message.")
        stream.write_all(AuthRequest(auth_type, self.session_token).encode())
        LOGGER.debug("Waiting for authorisation response.")
        auth_res = stream.read_message(AuthResponse.decode)

        if auth_res is None:
            LOGGER.warn("Received malformed message during connection.")
            raise ProtocolError(
                "Received a malformed message while trying to authenticate."
            )

        if auth_res.status != AuthStatus.Success:
            LOGGER.warn("Authentication failed!")
            raise AuthError(auth_res.status)
