import logging
import requests
import base64

from typing import Optional

from moatt_types.connect import AuthRequest, AuthResponse, AuthStatus, Token, SessionToken
from moatt_clients.streams import TcpStream

logger = logging.getLogger(__name__)

def register(api_url: str, token: Token) -> Optional[SessionToken]:
    headers = {"Authorization": f"Bearer {token.as_base64()}"}
    r = requests.post(f"{api_url}/register", headers=headers)

    if r.status_code != requests.codes.ok:
        logger.error(f"Registration failed. Received {r.status_code} status from server.")
        return None

    session_token = r.json()

    if type(session_token) != str:
        return None

    try:
        session_token = SessionToken(base64.b64decode(session_token, validate=True))
    except:
        logger.warn("Received a malformed session_token")
        return None

    return session_token

class Client:
    def __init__(self, session_token: SessionToken, token: Token, host, port):
        self.session_token = session_token
        self.token = token
        self.host = host
        self.port = port

    def _authenticate(self, stream: TcpStream) -> AuthStatus:
        logger.debug("Sending authorisation message.")
        stream.write_all(AuthRequest(self.session_token, self.token).encode())
        logger.debug("Waiting for authorisation response.")
        auth_res = AuthResponse.decode(stream.read_exactly(AuthResponse.LENGTH))

        if auth_res == None:
            logger.warn("Received malformed message during connection.")
            raise ValueError

        return auth_res.status
