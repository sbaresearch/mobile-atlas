import logging
import datetime

from flask import Response, request, jsonify, g, session
from moatt_server.rest import app, flask_http_auth, db
from moatt_server import auth
from moatt_server.rest.auth import protected
from typing import Optional

#from moatt_server.models import Sim, Provider, Imsi as DbImsi
import moatt_server.models as dbm
from moatt_types.connect import Imsi, Iccid

logger = logging.getLogger(__name__)

class Sim:
    def __init__(self, iccid: Iccid, imsi: Imsi):
        self.iccid = iccid
        self.imsi = imsi

# {""}
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
    if type(sims) != list or len(sims) == 0:
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
    session_token = auth.generate_session_token()
    #session['session_token'] = session_token.as_base64()

    provider = dbm.Provider(token_id=g._http_bearer_auth.token.as_base64(), session_token=session_token.as_base64())
    logger.debug(provider)
    db.session.add(provider)
    db.session.commit()

    resp = jsonify(session_token.as_base64())
    resp.set_cookie("session_token", session_token.as_base64())

    return resp

@app.route("/provider/sims", methods=["POST"])
@protected
def provider_register():
    try:
        sims = parse_sims(request.get_json())
    except ValueError:
        return Response(status=400)

    iccids = list(map(lambda x: x.iccid, sims.keys()))
    print(list(sims.keys()))
    existing_sims = list(db.session.scalars(db.select(dbm.Sim).where(dbm.Sim.iccid.in_(iccids))))
    new_iccids = set(iccids).difference(set([sim.iccid for sim in existing_sims]))
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    #session_token = auth.generate_session_token()
    #provider = dbm.Provider(token=g._http_bearer_auth.token, session_token=session_token)
    #provider = dbm.Provider(token="tokenplaceholder", session_token=session_token.as_base64())
    #db.session.add(provider)
    
    provider = g._session_token_auth.provider

    for sim in existing_sims:
        imsi = sims[Iccid(sim.iccid)].imsi.imsi

        if sim.provider != None:
            # TODO: A SIM card can only be published by one provider
            # to ensure that providers can reregister SIMs when they
            # lose connection without deregistering we need to implement
            # a heartbeat and a gc mechanism
            raise NotImplementedError

        sim.provider = provider
        db.session.add(dbm.Imsi(imsi=imsi,registered=now,sim=sim))

    for iccid in new_iccids:
        print(sims.keys())
        print(iccid)
        sim = dbm.Sim(
                iccid=iccid,
                imsi=[dbm.Imsi(imsi=sims[Iccid(iccid)].imsi.imsi, registered=now)],
                available=True,
                provider=provider
                )
        db.session.add(sim)


    db.session.commit()

    return Response(status=200)


# TODO: (un)marshalling Imsi/Iccid
#@app.route("/provider/foo", methods=["POST"])
#@protected
def provider_registe():
    try:
        sims = parse_sims(request.get_json())
    except ValueError:
        return Response(status=400)

    iccids = list(map(lambda x: x.iccid, sims.keys()))
    print(list(sims.keys()))
    existing_sims = list(db.session.scalars(db.select(dbm.Sim).where(dbm.Sim.iccid.in_(iccids))))
    new_iccids = set(iccids).difference(set([sim.iccid for sim in existing_sims]))
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    session_token = auth.generate_session_token()
    #provider = dbm.Provider(token=g._http_bearer_auth.token, session_token=session_token)
    provider = dbm.Provider(token="tokenplaceholder", session_token=session_token.as_base64())
    db.session.add(provider)

    for sim in existing_sims:
        imsi = sims[Iccid(sim.iccid)].imsi.imsi

        if sim.provider != None:
            # TODO: A SIM card can only be published by one provider
            # to ensure that providers can reregister SIMs when they
            # lose connection without deregistering we need to implement
            # a heartbeat and a gc mechanism
            raise NotImplementedError

        sim.provider = provider
        db.session.add(dbm.Imsi(imsi=imsi,registered=now,sim=sim))

    for iccid in new_iccids:
        print(sims.keys())
        print(iccid)
        sim = dbm.Sim(
                iccid=iccid,
                imsi=[dbm.Imsi(imsi=sims[Iccid(iccid)].imsi.imsi, registered=now)],
                available=True,
                provider=provider
                )
        db.session.add(sim)


    db.session.commit()

    return jsonify(session_token.as_base64())
