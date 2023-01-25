import enum, struct, logging
from typing import Optional

logger = logging.getLogger(__name__)

class Token:
    def __init__(self, token: bytes):
        assert len(token) == 25
        self.token = token

    def __eq__(self, other):
        return self.token == other.token

    def __hash__(self):
        return hash(self.token)

    def as_bytes(self):
        return self.token

@enum.unique
class IdentifierType(enum.Enum):
    Iccid = 0
    Imsi = 1

@enum.unique
class AuthStatus(enum.Enum):
    Success = 0
    InvalidToken = 1

@enum.unique
class ConnectStatus(enum.Enum):
    Success = 0
    NotFound = 1
    Forbidden = 2

@enum.unique
class ApduOp(enum.Enum):
    Apdu = 0
    Reset = 1

class ApduPacket:
    def __init__(self, op: ApduOp, payload: bytes):
        assert len(payload) < 32**2
        self.op = op
        self.payload = payload

    @staticmethod
    def decode(msg: bytes) -> Optional["ApduPacket"]:
        if len(msg) < 6:
            return None

        if msg[0] != 1:
            return None

        try:
            op = ApduOp(msg[1])
        except ValueError:
            return None

        l, = struct.unpack("!I", msg[2:6])

        if len(msg) != 6 + l:
            return None

        return ApduPacket(op, msg[6:])

    def encode(self) -> bytes:
        return struct.pack("!BBI", 1, self.op.value, len(self.payload)) + self.payload

class Imsi:
    def __init__(self, imsi):
        self.imsi = imsi

    def identifier_type(self):
        return IdentifierType.Imsi

    def encode(self) -> bytes:
        return self.imsi

class Iccid:
    def __init__(self, iccid):
        self.iccid = iccid

    def identifier_type(self):
        return IdentifierType.Iccid

    def encode(self) -> bytes:
        return self.iccid

class AuthRequest:
    LENGTH = 30

    def __init__(self, identifier: int, token: Token):
        self.identifier = identifier
        self.token = token

    @staticmethod
    def decode(msg: bytes) -> Optional["AuthRequest"]:
        if len(msg) != 30 or msg[0] != 1:
            return None

        try:
            identifier, = struct.unpack("!I", msg[1:5])
            return AuthRequest(identifier, Token(msg[5:]))
        except ValueError:
            return None

    def encode(self) -> bytes:
        return struct.pack("!BI", 1, self.identifier) + self.token.as_bytes()

class AuthResponse:
    LENGTH = 2

    def __init__(self, status: AuthStatus):
        self.status = status

    @staticmethod
    def decode(msg: bytes) -> Optional["AuthResponse"]:
        if len(msg) != 2 or msg[0] != 1:
            return None

        try:
            return AuthResponse(AuthStatus(msg[1]))
        except ValueError:
            return None

    def encode(self) -> bytes:
        return struct.pack("!BB", 1, self.status.value)

class ConnectRequest:
    def __init__(self, identifier):
        self.identifier = identifier

    @staticmethod
    def decode(msg: bytes) -> Optional["ConnectRequest"]:
        if len(msg) < 10 or msg[0] != 1:
            logger.debug("smaller 10 or msg[0] != 1")
            return None
        
        try:
            ident_type = IdentifierType(msg[1])
        except ValueError:
            logger.debug("ident_type = IdentifierType(msg[1])")
            return None

        if ident_type == IdentifierType.Imsi:
            if len(msg) != 10: 
                logger.debug("imsi: len != 10")
                return None
            return ConnectRequest(Imsi(msg[2:]))
        elif ident_type == IdentifierType.Iccid:
            if len(msg) != 11:
                logger.debug("iccid: len != 11")
                return None
            return ConnectRequest(Iccid(msg[2:]))

    def encode(self) -> bytes:
        return struct.pack("!BB", 1, self.identifier.identifier_type().value) + self.identifier.encode()

class ConnectResponse:
    LENGTH = 2

    def __init__(self, status: ConnectStatus): 
        self.status = status

    @staticmethod
    def decode(msg: bytes) -> Optional["ConnectResponse"]:
        if len(msg) != 2 or msg[0] != 1:
            return None

        try:
            return ConnectResponse(ConnectStatus(msg[1]))
        except ValueError:
            return None

    def encode(self) -> bytes:
        return struct.pack("!BB", 1, self.status.value)
