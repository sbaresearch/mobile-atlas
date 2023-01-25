import socket
import logging

from typing import Optional, Callable

from clients.client import Client
from clients.streams import ApduStream, TcpStream
from tunnelTypes.connect import (AuthStatus, ConnectRequest, ConnectResponse, ConnectStatus,
                                   IdentifierType, Token, Imsi, Iccid)

logger = logging.getLogger(__name__)

class ProviderClient(Client):
    def __init__(
            self,
            identifier: int,
            token: Token,
            host,
            port: int,
            cb: Callable[[ConnectRequest], ConnectStatus]
            ):
        self.cb = cb
        super().__init__(identifier, token, host, port)

    def wait_for_connection(self) -> Optional[tuple[Imsi | Iccid, ApduStream]]:
        logger.debug("Opening connection.")
        stream = TcpStream(socket.create_connection((self.host, self.port)))

        try:
            apdu_stream = self._wait_for_connection(stream)
        except:
            stream.close()
            return None

        if apdu_stream == None:
            stream.close()

        return apdu_stream

    def _wait_for_connection(self, stream: TcpStream) -> Optional[tuple[Imsi | Iccid, ApduStream]]:
        auth_status = self._authenticate(stream)

        if auth_status != AuthStatus.Success:
            logger.info("Authorisation failed!")
            return None

        logging.debug("Waiting for connection request.")
        conn_req = self._read_con_req(stream)

        if conn_req == None:
            logger.warn("Malformed connection request.")
            return None

        logger.debug(f"Received request for SIM: {conn_req.identifier}")

        status = self.cb(conn_req)

        logger.debug(f"Sending connection response with status: {status}")
        stream.write_all(ConnectResponse(status).encode())

        if status != ConnectStatus.Success:
            logger.info(f"Rejected request for SIM '{conn_req.identifier}' with '{status}'")
            return None

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
                raise NotImplemented
        except ValueError:
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
