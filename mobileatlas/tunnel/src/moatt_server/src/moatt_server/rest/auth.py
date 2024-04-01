import base64
import binascii
import logging
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from moatt_types.connect import Token

LOGGER = logging.getLogger(__name__)

bearer_token = HTTPBearer()


def session_token(
    token: Annotated[HTTPAuthorizationCredentials, Depends(bearer_token)]
) -> Token:
    try:
        return Token(base64.b64decode(token.credentials, validate=True))
    except binascii.Error:
        raise HTTPException(
            status_code=400, detail="Bearer token should be base64 encoded."
        )
