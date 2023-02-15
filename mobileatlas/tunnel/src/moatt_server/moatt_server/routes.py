import logging
import datetime

from flask import Response, request, jsonify
from moatt_server import app, flask_http_auth, db, auth
from typing import Optional

from moatt_server.models import Sim, Imsi, Provider

logger = logging.getLogger(__name__)

# {""}
def parse_sim(sim) -> dict[str, str]:
    if type(sim) != dict:
        raise ValueError
    if set(sim.keys()) != set(["imsi", "iccid"]):
        raise ValueError

    # TODO: parse imsi/iccid

    return sim

def parse_sims(sims) -> list[dict[str, str]]:
    if type(sims) != list:
        raise ValueError

    return sims


@app.route("/provider/register", methods=["POST"])
#@flask_http_auth.required
def provider_register():
    try:
        sims = parse_sims(request.get_json())
    except ValueError:
        return Response(status=400)

    sims = { sim["iccid"]: sim for sim in sims}

    print(list(sims.keys()))
    existing_sims = list(db.session.scalars(db.select(Sim).where(Sim.iccid.in_(sims.keys()))))
    new_iccids = set(sims.keys()).difference(set([sim.iccid for sim in existing_sims]))
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    session_token = auth.generate_session_token()
    provider = Provider(token="", session_token=session_token)
    db.session.add(provider)

    for sim in existing_sims:
        imsi = sims[sim.iccid]["imsi"]

        if sim.provider != None:
            # TODO: A SIM card can only be published by one provider
            # to ensure that providers can reregister SIMs when they
            # lose connection without deregistering we need to implement
            # a heartbeat and a gc mechanism
            raise NotImplemented

        sim.provider = provider
        db.session.add(Imsi(imsi=imsi,registered=now,sim=sim))

    for iccid in new_iccids:
        sim = Sim(
                iccid=iccid,
                imsi=[Imsi(imsi=sims[iccid]["imsi"], registered=now)],
                available=True,
                provider=provider
                )
        db.session.add(sim)


    db.session.commit()

    return jsonify(session_token)

