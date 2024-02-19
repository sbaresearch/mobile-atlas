from moatt_server.management import db
from moatt_server.models import MamToken, TokenScope, MamTokenAccessLog, TokenAction

import re
import base64
from flask import request, g, Request
from functools import wraps
from sqlalchemy import select

# TODO require token as decorator
# def require_token(func):
#     """Make sure token exists in headers"""
#     @functools.wraps(func)
#     def wrapper_require_token(*args, **kwargs):
#         if not get_token(request):
#             return "", 403
#         return func(*args, **kwargs)
#     return wrapper_require_token()


class TokenActivationHandler:
    @staticmethod
    def active(scope: TokenScope):
        raise NotImplementedError

    def validate_request(self, request):
        return

    def after_token_activation(self, session, token):
        return

    def before_token_deactivation(self, session, token):
        return

    def handle_activation_error(self, session, exc):
        return

def require_token(scope: TokenScope):
    def outer(f):
        @wraps(f)
        def inner(*args, **kwargs):
            token = check_token(request, scope)
            if token is not None:
                g.token = token
                db.session.add(MamTokenAccessLog(
                    token=token,
                    token_value=token.token_value(),
                    scope=scope,
                    action=TokenAction.Access,
                    ))
                return f(*args, **kwargs)
            else:
                return "", 403

        return inner
    return outer

# TODO: logging
def check_token(req: Request, scope: TokenScope) -> MamToken | None:
    if req.authorization is None or req.authorization.token is None:
        return None
    else:
        token = validate_token(req.authorization.token)

        if token is None:
            return None

        mamtoken = db.session.scalar(select(MamToken).where(MamToken.token == token))

        if mamtoken is None:
            return None

        if scope in mamtoken.scope:
            return mamtoken

        return None

def validate_token(token: str) -> str | None:
    try:
        if not token.isascii() or len(base64.b64decode(token, validate=True)) != 32:
            return None
    except:
        return None

    return token

def get_token(request):
    try:
        token = request.headers.get("Authorization").split(" ")[1]
        if not re.match("[a-zA-Z0-9]{32}$", token):
            return None
        return token
    except (IndexError, AttributeError):
        return None
