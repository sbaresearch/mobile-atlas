import logging
import socket
import ssl
import struct
from collections.abc import Callable
from typing import Optional, TypeVar

from moatt_types.connect import ApduOp, ApduPacket, PartialInput

from moatt_clients.errors import ProtocolError

LOGGER = logging.getLogger(__name__)


class RawStream:
    def __init__(self, socket):
        self._socket = socket
        self.buf = b""

    def getpeername(self):
        return self._socket.getpeername()

    def write_all(self, buf: bytes) -> None:
        self._socket.sendall(buf)

    T = TypeVar("T")

    def read_message(self, decoder: Callable[[bytes], T]) -> T:
        buf = b""

        while True:
            try:
                return decoder(buf)
            except PartialInput as e:
                r = self.read_exactly(e.bytes_missing)

                if len(r) == 0:
                    raise EOFError from None

                buf += r

    def read_exactly(self, n: int) -> bytes:
        while True:
            if len(self.buf) >= n:
                b = self.buf[:n]
                self.buf = self.buf[n:]
                return b

            if not self._fill_buf():
                raise EOFError

    def read(self, n: int = -1) -> bytes:
        if len(self.buf) == 0:
            self._fill_buf()

        if n == -1:
            b = self.buf
            self.buf = b""
            return b
        else:
            b = self.buf[:n]
            self.buf = self.buf[n:]
            return b

    def _fill_buf(self) -> bool:
        b = self._socket.recv(1024)
        print(f"Received: {b}")  # TODO
        if len(b) == 0:
            return False
        else:
            self.buf += b
            return True

    def close(self) -> None:
        self.buf = b""
        if isinstance(self._socket, ssl.SSLSocket):
            self._socket.unwrap()
        self._socket.shutdown(socket.SHUT_RDWR)
        self._socket.close()


class ApduStream:
    def __init__(self, stream: RawStream):
        self.stream = stream

    def getpeername(self):
        return self.stream.getpeername()

    def send_apdu(self, payload: bytes) -> None:
        """Wraps payload in an APDU packet and sends it.

        Parameters
        ----------
        payload
            Payload to send.
        """
        self.send(ApduPacket(ApduOp.Apdu, payload))

    def send_reset(self) -> None:
        """Sends a reset signal."""
        self.send(ApduPacket(ApduOp.Reset, b""))

    def send(self, packet: ApduPacket) -> None:
        """Sends an ApduPacket.

        Parameters
        ----------
        packet
            APDU to send.
        """
        self.stream.write_all(packet.encode())

    def recv(self) -> Optional[ApduPacket]:
        """Receive an APDU. Blocks until an APDU is received.

        Returns
        -------
        An APDU or None on EOF

        Raises
        ------
        EOFError
            If a partial APDU was received before EOF of the underlying stream.
        """
        buf = self.stream.read(n=6)

        if len(buf) == 0:
            return None

        missing = ApduStream._bytes_missing(buf)
        while missing > 0:
            r = self.stream.read(n=missing)
            assert len(r) <= missing

            if len(r) == 0:
                raise EOFError

            buf += r
            missing = ApduStream._bytes_missing(buf)

        p = ApduPacket.decode(buf)

        if p is None:
            raise ProtocolError("Received a malformed message.")

        return p

    def close(self) -> None:
        """Close the stream."""
        self.stream.close()

    @staticmethod
    def _bytes_missing(msg: bytes) -> int:
        if len(msg) < 6:
            return 6 - len(msg)

        (plen,) = struct.unpack("!I", msg[2:6])
        if len(msg) < 6 + plen:
            return (6 + plen) - len(msg)
        else:
            return 0