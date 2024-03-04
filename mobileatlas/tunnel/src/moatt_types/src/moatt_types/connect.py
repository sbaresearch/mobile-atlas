import base64
import enum
import logging
import struct

logger = logging.getLogger(__name__)

class PartialInput(Exception):
    def __init__(self, bytes_missing: int):
        self.bytes_missing = bytes_missing

class Token:
    def __init__(self, token: bytes):
        assert len(token) < 2**16
        self.token = token

    def __repr__(self):
        return f"Token({self.token})"

    def __eq__(self, other):
        if not isinstance(other, Token):
            return NotImplemented

        return self.token == other.token

    def __hash__(self):
        return hash(self.token)

    def as_bytes(self):
        return self.token

    def as_base64(self) -> str:
        return base64.b64encode(self.token).decode()


class SessionToken:
    def __init__(self, token: bytes):
        assert len(token) < 2**16
        self.token = token

    def __repr__(self):
        return f"Token({self.token})"

    def __eq__(self, other):
        if not isinstance(other, Token):
            return NotImplemented

        return self.token == other.token

    def __hash__(self):
        return hash(self.token)

    def as_bytes(self):
        return self.token

    def as_base64(self) -> str:
        return base64.b64encode(self.token).decode()


@enum.unique
class IdentifierType(enum.Enum):
    Id = 0
    Iccid = 1
    Imsi = 2
    Index = 3


@enum.unique
class AuthType(enum.Enum):
    Provider = 1
    Probe = 2


# TODO: add a status for expired creds?
@enum.unique
class AuthStatus(enum.Enum):
    Success = 0
    Unauthorized = 1
    NotRegistered = 3


@enum.unique
class ConnectStatus(enum.Enum):
    Success = 0
    NotFound = 1
    Forbidden = 2
    NotAvailable = 3
    ProviderTimedOut = 4


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
    def decode(msg: bytes) -> "ApduPacket":
        if len(msg) < 6:
            raise PartialInput(6 - len(msg))

        if msg[0] != 1:
            raise ValueError(f"Wrong version ({msg[0]}). Expected version 1.")

        op = ApduOp(msg[1])
        (plen,) = struct.unpack("!I", msg[2:6])

        if len(msg) < 6 + plen:
            raise PartialInput((6 + plen) - len(msg))

        if len(msg) > 6 + plen:
            raise ValueError(f"Expected message of length {6 + plen} but got {len(msg)} bytes.")

        return ApduPacket(op, msg[6:])

    def encode(self) -> bytes:
        return struct.pack("!BBI", 1, self.op.value, len(self.payload)) + self.payload


def _only_digits(msg: bytes) -> bool:
    def _is_digit(x: int):
        return x >= ord(b"0") and x <= ord(b"9")

    return all(map(_is_digit, msg))


class Imsi:
    _LEN = 15

    def __init__(self, imsi: str):
        if not _only_digits(imsi.encode()) or len(imsi) < 5 or len(imsi) > 15:
            raise ValueError

        self._imsi = imsi

    def __repr__(self):
        return f'Imsi("{self._imsi}")'

    def __eq__(self, other):
        if not isinstance(other, Imsi):
            return NotImplemented

        return self._imsi == other._imsi

    def __hash__(self):
        return hash(self._imsi)

    def identifier_type(self):
        return IdentifierType.Imsi

    @property
    def imsi(self) -> str:
        return self._imsi

    @staticmethod
    def decode(msg: bytes) -> "Imsi":
        if len(msg) < Imsi._LEN:
            raise PartialInput(Imsi._LEN - len(msg))

        if len(msg) > Imsi._LEN:
            raise ValueError(f"Expected IMSI to be encoded as {Imsi._LEN} bytes. (actual: {len(msg)})")

        msg = msg.rstrip(b"\x00")

        if not _only_digits(msg) or len(msg) < 5 or len(msg) > 15:
            raise ValueError("Expected IMSI to consist of 5 to 15 ascii digits.")

        return Imsi(msg.decode())

    def encode(self) -> bytes:
        imsi = self._imsi.encode()
        return imsi + b"\x00" * (Imsi._LEN - len(imsi))


class Iccid:
    _LEN = 20

    def __init__(self, iccid: str):
        if not _only_digits(iccid.encode()) or len(iccid) < 5 or len(iccid) > 20:
            raise ValueError

        self._iccid = iccid

    def __repr__(self):
        return f'Iccid("{self._iccid}")'

    def __eq__(self, other):
        if not isinstance(other, Iccid):
            return NotImplemented

        return self._iccid == other._iccid

    def __hash__(self):
        return hash(self._iccid)

    @property
    def iccid(self) -> str:
        return self._iccid

    def identifier_type(self) -> IdentifierType:
        return IdentifierType.Iccid

    @staticmethod
    def decode(msg: bytes) -> "Iccid":
        if len(msg) < Iccid._LEN:
            raise PartialInput(Iccid._LEN - len(msg))

        if len(msg) > Iccid._LEN:
            raise ValueError(f"Expected ICCID to be encoded as {Iccid._LEN} bytes. (actual: {len(msg)})")

        msg = msg.rstrip(b"\x00")

        if not _only_digits(msg) or len(msg) < 5 or len(msg) > 20:
            raise ValueError("Expected IMSI to consist of 5 to 20 ascii digits.")

        return Iccid(msg.decode())

    def encode(self) -> bytes:
        iccid = self._iccid.encode()
        return iccid + b"\x00" * (Iccid._LEN - len(iccid))


class SimId:
    _LEN = 8

    def __init__(self, id: int):
        assert id < 2 ** (8 * SimId._LEN)

        self._id = id


    def __repr__(self):
        return f"SimId({self._id})"

    def __eq__(self, other):
        if not isinstance(other, SimId):
            return NotImplemented

        return self._id == other._id

    def __hash__(self):
        return hash(self._id)

    @property
    def id(self) -> int:
        return self._id

    def identifier_type(self) -> IdentifierType:
        return IdentifierType.Id

    @staticmethod
    def decode(msg: bytes) -> "SimId":
        if len(msg) < SimId._LEN:
            raise PartialInput(SimId._LEN - len(msg))

        if len(msg) > SimId._LEN:
            raise ValueError(f"Expected 64-bit integer value.")

        return SimId(struct.unpack("!Q", msg)[0])

    def encode(self) -> bytes:
        return struct.pack("!Q", self._id)


class SimIndex:
    _LEN = 8

    def __init__(self, idx: int):
        assert id < 2 ** (8 * SimIndex._LEN)

        self._idx = idx

    def __repr__(self):
        return f"SimIndex({self._idx})"

    def __eq__(self, other):
        if not isinstance(other, SimIndex):
            return NotImplemented

        return self._idx == other._idx

    def __hash__(self):
        return hash(self._idx)

    @property
    def index(self) -> int:
        return self._idx

    @staticmethod
    def decode(msg: bytes) -> "SimIndex":
        if len(msg) < SimIndex._LEN:
            raise PartialInput(SimIndex._LEN - len(msg))

        if len(msg) > SimIndex._LEN:
            raise ValueError(f"Expected 64-bit integer value.")

        return SimIndex(struct.unpack("!Q", msg)[0])

    def encode(self) -> bytes:
        return struct.pack("!Q", self._idx)


class AuthRequest:
    _MIN_LEN = 4

    def __init__(self, auth_type: AuthType, session_token: SessionToken):
        self.auth_type = auth_type
        self.session_token = session_token

    @staticmethod
    def decode(msg: bytes) -> "AuthRequest":
        if len(msg) < AuthRequest._MIN_LEN:
            raise PartialInput(AuthRequest._MIN_LEN - len(msg))

        (version, auth_type, plen) = struct.unpack("!BBH", msg[:4])

        if version != 1:
            raise ValueError(f"Wrong version ({version}). Expected version 1.")

        if len(msg) < plen + 4:
            raise PartialInput((plen + 4) - len(msg))

        if len(msg) != plen + 4:
            raise ValueError

        return AuthRequest(AuthType(auth_type), SessionToken(msg[4:]))

    def encode(self) -> bytes:
        token_bytes = self.session_token.as_bytes()
        return struct.pack("!BBH", 1, self.auth_type.value, len(token_bytes)) + token_bytes


class AuthResponse:
    _LEN = 2

    def __init__(self, status: AuthStatus):
        self.status = status

    @staticmethod
    def decode(msg: bytes) -> "AuthResponse":
        if len(msg) < AuthResponse._LEN:
            raise PartialInput(AuthResponse._LEN - len(msg))

        if len(msg) > AuthResponse._LEN:
            raise ValueError(f"Expected message of length {AuthResponse._LEN} but got {len(msg)} bytes.")

        if msg[0] != 1:
            raise ValueError(f"Wrong version ({msg[0]}). Expected version 1.")

        return AuthResponse(AuthStatus(msg[1]))

    def encode(self) -> bytes:
        return struct.pack("!BB", 1, self.status.value)


@enum.verify(enum.NAMED_FLAGS)
class ConnectionRequestFlags(enum.Flag):
    DEFAULT = 0
    NO_WAIT = 1


class ConnectRequest:
    def __init__(
            self, identifier, flags: ConnectionRequestFlags = ConnectionRequestFlags.DEFAULT # TODO check compat
    ):
        self.flags = flags
        self.identifier = identifier

    @staticmethod
    def decode(msg: bytes) -> "ConnectRequest":
        if len(msg) < 3:
            raise PartialInput(3 - len(msg))

        if msg[0] != 1:
            raise ValueError(f"Wrong version ({msg[0]}). Expected version 1.")

        flags = ConnectionRequestFlags(msg[1])
        ident_type = IdentifierType(msg[2])

        if ident_type == IdentifierType.Id:
            identifier = SimId.decode(msg[3:])
        elif ident_type == IdentifierType.Imsi:
            identifier = Imsi.decode(msg[3:])
        elif ident_type == IdentifierType.Iccid:
            identifier = Iccid.decode(msg[3:])
        elif ident_type == IdentifierType.Index:
            identifier = SimIndex.decode(msg[3:])
        else:
            raise NotImplementedError

        return ConnectRequest(identifier, flags)

    def encode(self) -> bytes:
        return (
            struct.pack(
                "!BBB", 1, self.flags.value, self.identifier.identifier_type().value
            )
            + self.identifier.encode()
        )


class ConnectResponse:
    _LEN = 2

    def __init__(self, status: ConnectStatus):
        self.status = status

    @staticmethod
    def decode(msg: bytes) -> "ConnectResponse":
        if len(msg) < ConnectResponse._LEN:
            raise PartialInput(ConnectResponse._LEN - len(msg))

        if len(msg) > ConnectResponse._LEN:
            raise ValueError(f"Expected message of length {ConnectResponse._LEN} but got {len(msg)} bytes.")

        if msg[0] != 1:
            raise ValueError(f"Wrong version ({msg[0]}). Expected version 1.")

        return ConnectResponse(ConnectStatus(msg[1]))

    def encode(self) -> bytes:
        return struct.pack("!BB", 1, self.status.value)
