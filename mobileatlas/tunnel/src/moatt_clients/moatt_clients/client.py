import logging

from moatt_types.connect import AuthRequest, AuthResponse, AuthStatus, Token
from moatt_clients.streams import TcpStream

logger = logging.getLogger(__name__)

class Client:
    def __init__(self, identifier: int, token: Token, host, port):
        self.identifier = identifier
        self.token = token
        self.host = host
        self.port = port

    def _authenticate(self, stream: TcpStream) -> AuthStatus:
        logger.debug("Sending authorisation message.")
        stream.write_all(AuthRequest(self.identifier, self.token).encode())
        logger.debug("Waiting for authorisation response.")
        auth_res = AuthResponse.decode(stream.read_exactly(AuthResponse.LENGTH))

        if auth_res == None:
            logger.warn("Received malformed message during connection.")
            raise ValueError

        return auth_res.status
