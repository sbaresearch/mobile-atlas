from flask import request, Response, g
from types import SimpleNamespace
import base64
from moatt_types.connect import Token
from moatt_server.auth import valid
from functools import wraps

class HttpAuth:
    def __init__(self, app=None):
        self.app = app
        #if app is not None:
        #    self.init_app(app)

    #def init_app(self, app):
    #    pass

def required(f):
    @wraps(f)
    def auth(*args, **kwargs):
        auth_header = request.headers.get("Authorization") # TODO: multiple headers

        if auth_header == None:
            return Response(status=401, headers={"WWW-Authenticate": "Bearer"})

        if not auth_header.startswith("Bearer ") or len(auth_header.split(' ')) != 2:
            return Response(
                    status=400,
                    headers={"WWW-Authenticate": "Bearer error=\"invalid_request\""}
                    ) # TODO WWW-Auth header

        try:
            token = Token(base64.b64decode(auth_header.split(' ')[1]))

            if token == None: # TODO refactor error handling
                raise ValueError
        except:
            return Response(
                    status=400,
                    headers={"WWW-Authenticate": "Bearer error=\"invalid_request\""}
                    )

        if not valid(token):
            return Response(
                    status=401,
                    headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""}
                    )

        g._http_bearer_auth = SimpleNamespace()
        g._http_bearer_auth.valid_token = True

        return f(*args, **kwargs)

    return auth
