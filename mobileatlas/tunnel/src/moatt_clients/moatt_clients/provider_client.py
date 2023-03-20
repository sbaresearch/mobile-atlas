import socket
import requests
import logging

from typing import Optional, Callable, Union, List, Tuple

from moatt_clients.client import Client
from moatt_clients.streams import ApduStream, TcpStream
from moatt_types.connect import (AuthStatus, ConnectRequest, ConnectResponse, ConnectStatus,
                                   IdentifierType, Imsi, Iccid, SessionToken)

logger = logging.getLogger(__name__)

def register_sims(api_url: str, session_token: SessionToken, sims: List[dict]) -> Optional[SessionToken]:
    if session_token is None:
        return None

    cookies = dict(session_token=session_token.as_base64())
    r = requests.put(f"{api_url}/provider/sims", json=sims, cookies=cookies)

    if r.status_code != requests.codes.ok:
        logger.error(f"Registration failed. Received {r.status_code} status from server.")
        return None

    return session_token


class ProviderClient(Client):
    def __init__(
            self,
            session_token: SessionToken,
            host,
            port: int,
            cb: Callable[[ConnectRequest], ConnectStatus],
            ):
        self.cb = cb
        super().__init__(session_token, host, port)

    def wait_for_connection(self) -> Optional[Tuple[Union[Imsi, Iccid], ApduStream]]:
        logger.debug("Opening connection.")
        stream = TcpStream(socket.create_connection((self.host, self.port)))

        try:
            apdu_stream = self._wait_for_connection(stream)
        except Exception as e:
            logger.warn(f"Exception was raised while waiting for connection: {e}")
            stream.close()
            return None

        if apdu_stream is None:
            logger.debug("APDU stream is none")
            stream.close()

        return apdu_stream

    def _wait_for_connection(self, stream: TcpStream) -> Optional[Tuple[Union[Imsi, Iccid], ApduStream]]:
        auth_status = self._authenticate(stream)

        if auth_status != AuthStatus.Success:
            logger.info("Authorisation failed!")
            return None

        logging.debug("Waiting for connection request.")
        conn_req = self._read_con_req(stream)

        if conn_req is None:
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
                raise NotImplementedError
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
