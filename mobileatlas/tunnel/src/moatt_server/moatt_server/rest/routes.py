import logging
import datetime
import base64

from flask import Response, request, jsonify, g
from moatt_server.rest import app, flask_http_auth, db
from moatt_server import auth
from moatt_server.rest.auth import protected
from moatt_types.connect import SessionToken

import moatt_server.models as dbm
from moatt_types.connect import Imsi, Iccid

logger = logging.getLogger(__name__)

class Sim:
    def __init__(self, iccid: Iccid, imsi: Imsi):
        self.iccid = iccid
        self.imsi = imsi

def parse_sim(sim) -> Sim:
    if type(sim) != dict or len(sim) != 2:
        raise ValueError

    try:
        iccid = sim["iccid"]
        imsi = sim["imsi"]
    except:
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

# TODO: limit the number of clients that can simultaneously use the same token
@app.route("/register", methods=["POST"])
@flask_http_auth.required
def register():
    token = g._http_bearer_auth.token
    session_token = auth.generate_session_token()
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    db.session.add(dbm.SessionToken(
        value=session_token.as_base64(),
        created=now,
        last_access=now,
        token_id=token.as_base64()
        ))
    db.session.commit()

    resp = jsonify(session_token.as_base64())
    resp.set_cookie("session_token", session_token.as_base64())

    return resp

@app.route("/deregister", methods=["DELETE"])
def deregister():
    session_token = request.cookies.get("session_token")

    if session_token == None:
        return Response(status=200)

    try:
        session_token = SessionToken(base64.b64decode(session_token))
    except ValueError:
        return Response(status=400)

    session_token = db.session.get(dbm.SessionToken, session_token.as_base64())

    if session_token.provider != None:
        db.session.delete(session_token.provider)

    db.session.delete(session_token)
    db.session.commit()

    return Response(status=200)

@app.route("/provider/sims", methods=["PUT"])
@protected
def provider_register():
    try:
        sims = parse_sims(request.get_json())
    except ValueError:
        return Response(status=400)

    session = db.session.get(dbm.SessionToken, g._session_token_auth.session_token.as_base64())

    if session.provider == None:
        provider = dbm.Provider(
                session_token_id=session.value
                )
        db.session.add(provider)
    else:
        provider = session.provider

    iccids = list(map(lambda x: x.iccid, sims.keys()))

    removed_sims = db.session.scalars(
            db.select(dbm.Sim)\
                    .where(dbm.Sim.provider_id == provider.id)\
                    .where(dbm.Sim.iccid.not_in(iccids))
            )

    for sim in removed_sims:
        sim.provider = None

    if len(sims) == 0:
        db.session.commit()
        return Response(status=200)

    existing_sims = list(db.session.scalars(db.select(dbm.Sim).where(dbm.Sim.iccid.in_(iccids))))
    new_iccids = set(iccids).difference(set([sim.iccid for sim in existing_sims]))
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    for sim in existing_sims:
        imsi = sims[Iccid(sim.iccid)].imsi.imsi

        if sim.provider != None:
            if sim.provider.id == provider.id:
                continue

            if sim.provider.allow_reregistration == False:
                return Response(status=403)

        sim.provider = provider
        db.session.add(dbm.Imsi(imsi=imsi,registered=now,sim=sim))

    for iccid in new_iccids:
        sim = dbm.Sim(
                iccid=iccid,
                imsi=[dbm.Imsi(imsi=sims[Iccid(iccid)].imsi.imsi, registered=now)],
                available=True,
                provider=provider
                )
        db.session.add(sim)


    db.session.commit()

    return Response(status=200)
