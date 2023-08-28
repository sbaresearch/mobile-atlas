import logging
import base64

from flask import Response, request, jsonify, g
from moatt_server.rest import app, flask_http_auth, db
from moatt_server import auth
from moatt_server.auth import Sim
from moatt_server.rest.auth import protected
from moatt_types.connect import SessionToken

from moatt_types.connect import Imsi, Iccid

logger = logging.getLogger(__name__)

def parse_sim(sim) -> Sim:
    if type(sim) != dict or len(sim) != 2:
        raise ValueError

    try:
        iccid = sim["iccid"]
        imsi = sim["imsi"]
    except KeyError:
        raise ValueError

    return Sim(Iccid(iccid), Imsi(imsi))

def parse_sims(sims) -> dict[Iccid, Sim]:
    if type(sims) != list:
        raise ValueError

    parsed_sims = {}

    for sim in sims:
        parsed_sim = parse_sim(sim)

        if parsed_sim.iccid in parsed_sims:
            raise ValueError

        parsed_sims[parsed_sim.iccid] = parsed_sim

    return parsed_sims

# TODO: endpoint to request new session token to replace expiring s. token
@app.route("/register", methods=["POST"])
@flask_http_auth.required
def register():
    token = g._http_bearer_auth.token
    session_token = auth.insert_new_session_token(db.session, token.as_base64())

    resp = jsonify(session_token.as_base64())
    resp.set_cookie("session_token", session_token.as_base64())

    return resp

@app.route("/deregister", methods=["DELETE"])
def deregister():
    session_token = request.cookies.get("session_token")

    if session_token is None:
        return Response(status=200)

    try:
        session_token = SessionToken(base64.b64decode(session_token))
    except ValueError:
        return Response(status=400)

    auth.deregister_session(db.session, session_token)

    return Response(status=200)

# TODO: return already registered sims on error
@app.route("/provider/sims", methods=["PUT"])
@protected
def provider_register():
    try:
        sims = parse_sims(request.get_json())
    except ValueError:
        return Response(status=400)

    try:
        auth.register_provider(db.session, g._session_token_auth.session_token, sims)
    except auth.AuthError:
        return Response(status=403)

    return Response(status=200)
