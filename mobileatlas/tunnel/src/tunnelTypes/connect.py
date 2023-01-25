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

#def _is_valid_imsi(msg: bytes) -> bool:
#    def _is_digit(x: int):
#        return x >= ord(b'0') and x <= ord(b'9')
#
#    return len(msg) >= 5 and len(msg) <= 15 and all(map(_is_digit, msg))

def _only_digits(msg: bytes) -> bool:
    def _is_digit(x: int):
        return x >= ord(b'0') and x <= ord(b'9')

    return all(map(_is_digit, msg))

class Imsi:
    LENGTH = 15

    def __init__(self, imsi: str):
        if not _only_digits(imsi.encode()) or len(imsi) < 5 or len(imsi) > 15:
            raise ValueError

        self.imsi = imsi

    def identifier_type(self):
        return IdentifierType.Imsi

    @staticmethod
    def decode(msg: bytes) -> Optional["Imsi"]:
        if len(msg) != Imsi.LENGTH:
            return None

        msg = msg.rstrip(b'\x00')

        if not _only_digits(msg) or len(msg) < 5 or len(msg) > 15:
            return None

        return Imsi(msg.decode())

    def encode(self) -> bytes:
        return self.imsi.encode() + b'\x00' * (Imsi.LENGTH - len(self.imsi))

class Iccid:
    LENGTH = 20

    def __init__(self, iccid: str):
        if not _only_digits(iccid.encode()) or len(iccid) < 5 or len(iccid) > 20:
            raise ValueError

        self.iccid = iccid

    def identifier_type(self):
        return IdentifierType.Iccid

    @staticmethod
    def decode(msg: bytes) -> Optional["Iccid"]:
        if len(msg) != Iccid.LENGTH:
            return None

        msg = msg.rstrip(b'\x00')

        if not _only_digits(msg) or len(msg) < 5 or len(msg) > 20:
            return None

        return Iccid(msg.decode())

    def encode(self) -> bytes:
        return self.iccid.encode() + b'\x00' * (Iccid.LENGTH - len(self.iccid))

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
<<<<<<< HEAD
    def __init__(self, identifier):
=======
    MIN_LENGTH = 17

    def __init__(self, identifier: Imsi | Iccid):
>>>>>>> 271361d19b6dd01acf2631a8fd461a467f94036b
        self.identifier = identifier

    @staticmethod
    def decode(msg: bytes) -> Optional["ConnectRequest"]:
        if len(msg) < 17 or msg[0] != 1:
            return None

        try:
            ident_type = IdentifierType(msg[1])
        except ValueError:
            return None

        if ident_type == IdentifierType.Imsi:
            if len(msg) != 2 + Imsi.LENGTH:
                return None

            imsi = Imsi.decode(msg[2:])

            if imsi == None:
                return None

            return ConnectRequest(imsi)
        elif ident_type == IdentifierType.Iccid:
            if len(msg) != 2 + Iccid.LENGTH:
                return None

            iccid = Iccid.decode(msg[2:])

            if iccid == None:
                return None

            return ConnectRequest(iccid)

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
