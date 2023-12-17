import base64
import binascii
import datetime
from functools import wraps
from types import SimpleNamespace

from flask import Response, g, request
from moatt_types.connect import SessionToken, Token

from .. import models as dbm
from ..auth import sync_get_session_token
from . import db


def protected(f):
    @wraps(f)
    def auth(*args, **kwargs):
        session_token = request.cookies.get("session_token")

        if session_token is None:
            return Response(status=401)  # TODO: add www-authenticate header

        try:
            session_token = SessionToken(base64.b64decode(session_token, validate=True))
        except (binascii.Error, ValueError):
            return Response(status=401)  # TODO: add www-authenticate header

        # provider = sync_get_registration(db.session, session_token)
        sess = sync_get_session_token(db.session, session_token)

        if (
            not isinstance(sess, dbm.SessionToken)
            or sess.value != session_token.as_base64()
        ):
            return Response(status=403)

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        if sess.token.active is False or (
            sess.token.expires is not None and sess.token.expires < now
        ):
            return Response(status=403)

        try:
            token = Token(base64.b64decode(sess.token.value, validate=True))
        except (binascii.Error, ValueError):
            return Response(status=500)

        g._session_token_auth = SimpleNamespace()
        g._session_token_auth.session_token = session_token
        g._session_token_auth.session = sess
        g._session_token_auth.token = token

        return f(*args, **kwargs)

    return auth
