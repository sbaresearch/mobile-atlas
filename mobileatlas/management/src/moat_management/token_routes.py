from moatt_server.management import app, db, basic_auth
from moatt_server.utils import now
from moatt_server.models import MamTokenAccessLog, MamToken, TokenScope, TokenAction
from moatt_server.management.wireguard_routes import WgTokenActivationHandler
from moatt_server.management.probe_routes import ProbeTokenActivationHandler
from moatt_server.management import token_auth
from flask import request, render_template, g
from sqlalchemy import select

import base64
import re

TOKEN_ACTIVATION_HANDLERS = [
        WgTokenActivationHandler,
        ProbeTokenActivationHandler
        ]

@app.route("/tokens", methods=["GET"])
def token_index():
    tokens = db.session.scalars(select(MamToken).where(MamToken.token != None))
    token_reqs = db.session.scalars(select(MamToken).where(MamToken.token == None))
    #print(type(list(token_reqs)[0].logs[0].action))
    return render_template(
            "tokens.html",
            tokens=tokens,
            token_reqs=token_reqs,
            TokenAction=TokenAction,
            )

@app.route("/tokens/register", methods=["POST"])
def token_register():
    if "token_candidate" not in request.values \
            or "mac" not in request.values \
            or "scope" not in request.values:
        return "token_candidate/mac/scope missing", 400

    token_candidate = request.values["token_candidate"]
    try:
        if not token_candidate.isascii() or len(base64.b64decode(token_candidate, validate=True)) != 32:
            return "token invalid", 400
    except:
        return "token invalid", 400

    mac = request.values["mac"]
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
            return "mac invalid, use 11:22:33:44:55:66", 400

    try:
        scope = get_scope(request.values["scope"])
    except Exception:
        return "invalid scope", 400

    new_cand = add_token_candidate(token_candidate, scope, mac)

    if new_cand is not None:
        prune_candidates()

    db.session.commit()

    if new_cand is not None:
        return "", 201
    else:
        return "", 200

@app.route("/tokens/active", methods=["GET"])
@token_auth.require_token(TokenScope(0))
def token_active():
    return "", 200

@app.route("/tokens/revoke", methods=["DELETE"])
@token_auth.require_token(TokenScope(0))
def revoke():
    delete_token(db.session, g.token.token)
    db.session.commit()

    return "", 200

# TODO: log change
@app.route("/tokens/scope", methods=["POST"])
@basic_auth.required
def change_scope():
    if "scope" not in request.values or "token" not in request.values:
        return "token/scope missing", 400

    token = request.values["token"]
    if not valid_token(token):
        return "invalid token", 400

    try:
        scope = get_scope(request.values["scope"])
    except:
        return "invalid scope", 400

    token = get_token_by_value(db.session, token)

    if token is None:
        return "token does not exist", 404

    token.scope = scope
    db.session.commit()

    return "", 200

@app.route("/tokens/activate", methods=["POST"])
@basic_auth.required
def token_activate():

    if "token_candidate" not in request.values \
            or "scope" not in request.values:
        return "token_candidate/scope missing", 400

    token_candidate = request.values["token_candidate"]
    try:
        if not token_candidate.isascii() or len(base64.b64decode(token_candidate, validate=True)) != 32:
            return "invalid token", 400
    except:
        return "invalid token", 400

    try:
        scope = get_scope(request.values["scope"])
    except:
        return "invalid scope", 400

    active_handlers = [h() for h in TOKEN_ACTIVATION_HANDLERS if h.active(scope)]
    for handler in active_handlers:
        resp = handler.validate_request(request)

        if resp is not None:
            return resp

    token = db.session.scalar(select(MamToken).where(MamToken.token_candidate == token_candidate))

    if token is None:
        token = add_token_candidate(token_candidate, scope)
        
        if token is None:
            raise Exception("Failed to create new token candidate.")

    if token.scope != scope:
        return "'scope' does not match the requested scope", 400

    token.activate(db.session)

    for handler in active_handlers:
        resp = handler.after_token_activation(db.session, token)

        if resp is not None:
            return resp

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        for handler in active_handlers:
            resp = handler.handle_activation_error(db.session, e)

            if resp is not None:
                return resp

        raise e

    return "", 200

@app.route('/tokens/deactivate', methods=['POST'])
@basic_auth.required
def token_deactivate():
    if 'token' not in request.values:
        return "missing token", 400

    token = request.values['token']
    try:
        if not token.isascii() or len(base64.b64decode(token, validate=True)) != 32:
            return "invalid token", 400
    except:
        return "invalid token", 400

    delete_token(db.session, token)
    db.session.commit()

    return "", 200

def get_token_by_value(session, value: str) -> None | MamToken:
    return session.scalar(
            select(MamToken)
            .where(
                (MamToken.token == value) |
                (MamToken.token_candidate == value)
                )
            )


def valid_token(token):
    try:
        if token.isascii() and len(base64.b64decode(token, validate=True)) == 32:
            return True
    except:
        pass

    return False

def delete_token(session, token):
    # we have to use Session.delete here
    # because using Session.execute with
    # sql.expression.delete does not
    # trigger configured cascades
    tokens = session.scalars(
            select(MamToken)
            .where((MamToken.token == token) |
                   (MamToken.token_candidate == token)
                  )
            )

    time = now()
    for t in tokens:
        session.add(MamTokenAccessLog(
            token_value=t.token_value(),
            scope=t.scope,
            action=TokenAction.Deactivated,
            time=time,
            ))
        session.delete(t)

def prune_candidates():
    old_tokens = db.session.scalars(
            select(MamToken)
            .outerjoin(MamToken.logs)
            .where(MamToken.token == None)
            .order_by(MamTokenAccessLog.time.desc())
            .offset(10) # TODO: add config var
            .distinct()
            )

    for token in old_tokens:
        db.session.delete(token)

def get_scope(scope):
    s = TokenScope(int(scope))

    if s.value == 0:
        raise ValueError

    return s
    #scopes = map(lambda x: TokenScope[x], scopes.split('|'))
    #return reduce(lambda x, y: x | y, scopes)

def add_token_candidate(token_candidate, scope, mac=None):
    tc = db.session.scalar(
            select(MamToken)
            .where(
                    (MamToken.token_candidate == token_candidate) |
                    (MamToken.token == token_candidate)
                  )
            )

    if tc is not None:
        return

    t = MamToken(token_candidate=token_candidate, scope=scope, mac=mac)
    l = MamTokenAccessLog(token=t, token_value=token_candidate, scope=scope, action=TokenAction.Registered)
    db.session.add(t)
    db.session.add(l)

    return t
