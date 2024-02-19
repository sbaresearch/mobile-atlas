import base64
import binascii
import logging
import ssl
from typing import Optional

import requests

from moatt_clients.errors import AuthError, ProtocolError
from moatt_clients.streams import RawStream
from moatt_types.connect import (
    AuthRequest,
    AuthResponse,
    AuthStatus,
    SessionToken,
    Token,
)

logger = logging.getLogger(__name__)


def deregister(api_url: str, session_token: SessionToken) -> bool:
    """Deregister a session token.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    session_token
        Session token to deregister.

    Returns
    -------
    Whether deregistration was successful.
    """
    cookies = dict(session_token=session_token.as_base64())
    r = requests.delete(f"{api_url}/deregister", cookies=cookies)

    if r.status_code != requests.codes.ok:
        return False
    else:
        return True


def register(api_url: str, token: Token) -> SessionToken:
    """Try to register a client using a valid token.

    Parameters
    ----------
    api_url
        API base URL (e.g., 'https://example.com/api/v1')
    token
        API access token

    Returns
    -------
    The session token returned by the server or None if registration failed.

    Raises
    ------
    requests.HTTPError
        If the server responds with an HTTP error code.
    ValueError
        If the server's response is malformed.
    """
    headers = {"Authorization": f"Bearer {token.as_base64()}"}
    r = requests.post(f"{api_url}/register", headers=headers)

    try:
        r.raise_for_status()
    except requests.HTTPError:
        logger.error(
            f"Registration failed. Received {r.status_code} status from server."
        )
        raise

    session_token = r.json()

    if not isinstance(session_token, str):
        raise ValueError

    try:
        session_token = SessionToken(base64.b64decode(session_token, validate=True))
    except (binascii.Error, ValueError):
        logger.error("Received a malformed session_token")
        raise ValueError from None

    return session_token


class Client:
    def __init__(
        self,
        session_token: SessionToken,
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

    def _authenticate(self, stream: RawStream) -> None:
        logger.debug("Sending authorisation message.")
        stream.write_all(AuthRequest(self.session_token).encode())
        logger.debug("Waiting for authorisation response.")
        auth_res = AuthResponse.decode(stream.read_exactly(AuthResponse.LENGTH))

        if auth_res is None:
            logger.warn("Received malformed message during connection.")
            raise ProtocolError(
                "Received a malformed message while trying to authenticate."
            )

        if auth_res.status != AuthStatus.Success:
            logger.warn("Authentication failed!")
            raise AuthError(auth_res.status)
