from flask import request, Response, g
from types import SimpleNamespace
import base64
from functools import wraps

from moatt_types.connect import SessionToken, Token

from moatt_server.auth import sync_get_registration

from moatt_server.rest import db

import moatt_server.models as dbm

def protected(f):
    @wraps(f)
    def auth(*args, **kwargs):
        session_token = request.cookies.get("session_token")

        if session_token == None:
            return Response(status=401) # TODO: add www-authenticate header

        try:
            session_token = SessionToken(base64.b64decode(session_token))
        except:
            return Response(status=401) # TODO: add www-authenticate header

        provider = sync_get_registration(db.session, session_token)

        if provider == None or type(provider) != dbm.Provider or provider.session_token != session_token.as_base64():
            return Response(status=403)

        # TODO: check expiration
        if provider.token.active == False:
            return Response(status=403)

        try:
            token = Token(base64.b64decode(provider.token.value))
        except:
            return Response(status=500)

        g._session_token_auth = SimpleNamespace()
        g._session_token_auth.valid_session_token = True
        g._session_token_auth.session_token = session_token
        g._session_token_auth.token = token
        g._session_token_auth.provider_id = provider.id
        g._session_token_auth.provider = provider

        return f(*args, **kwargs)

    return auth
