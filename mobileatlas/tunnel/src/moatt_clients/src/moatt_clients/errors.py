from typing import Union

from moatt_types.connect import AuthStatus, ConnectStatus, Iccid, Imsi


class SimRequestError(Exception):
    def __init__(self, status: ConnectStatus, id: Union[Imsi, Iccid]):
        self.status = status
        self.id = id

    def __str__(self):
        return f"Connection with SIM card {self.id} could not be established. ({self.status})"


class AuthError(Exception):
    def __init__(self, status: AuthStatus):
        self.status = status

    def __str__(self):
        return f"Authentication failed with error: {self.status}"


class ProtocolError(Exception):
    def __init__(self, msg=None):
        self.msg = msg

    def __str__(self):
        return (
            "Received an invalid message." + f" ({self.msg})"
            if self.msg is not None
            else ""
        )
