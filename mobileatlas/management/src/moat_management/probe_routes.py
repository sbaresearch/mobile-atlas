from flask import jsonify, request
from sqlalchemy import select, exc as sqlexc
from moatt_server.management import app, redis_client, db, token_auth
from moatt_server import utils
from moatt_server.models import (
        Probe,
        ProbeServiceStartupLog,
        ProbeStatus,
        ProbeStatusType,
        ProbeSystemInformation,
        TokenScope,
        )
from datetime import timedelta
from json import dumps
from flask import g
import time
import re

"""
Endpoints called from the Measurement Probe are listed in this file
"""

@app.route('/probe/startup', methods=['POST'])
@token_auth.require_token(TokenScope.Probe)
def startup_log():
    if 'mac' not in request.values:
        return "", 400

    mac = request.values['mac']
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
        return "", 400

    # Check if mac is known in Probe List, otherwise deny
    #probe = list(db.session.scalars(select(Probe).join(Probe.token).where(MamToken.mac == mac).distinct())) # TODO: test
    #stmt = select(Probe).join(Probe.token).where(MamToken.mac == mac).distinct()
    #print(stmt)
    #macs = list(db.session.scalars(stmt))
    #print(macs)
    #query = db.session.query(Probe.mac.distinct().label("mac"))
    #macs = [row.mac for row in query.all()]
    if g.token.mac != mac:
        return "", 400

    # Create a log entry
    prl = ProbeServiceStartupLog(
            probe_id=g.token.probe[0].id,
            mac=mac,
            timestamp=utils.now())
    db.session.add(prl)
    db.session.commit()

    return "", 200

@app.route('/probe/poll', methods=['POST'])
@token_auth.require_token(TokenScope.Probe)
def probe_poll():
    """
    The long poll endpoint for the probe
    """
    if not g.token.probe:
        return "", 403
    probe = g.token.probe[0]
    probe.last_poll = utils.now()

    # Include a status update
    #
    # (1) No last status - create a new status
    # (2) Got last status
    #     (2a) Expired - Finish old status - create new status
    #     (2b) Active - Prolong active status
    # Todo move this functionality
    #ps = ProbeStatus.query.filter_by(probe_id=probe.id, active=True).first()
    ps = db.session.scalar(
            select(ProbeStatus)
            .where((ProbeStatus.probe_id == probe.id) & (ProbeStatus.active == True))
            )
    interval = timedelta(seconds=app.config["LONG_POLLING_INTERVAL"])
    now = utils.now()

    if ps:
        # Case (2b)
        if ps.status == ProbeStatusType.online and ps.end + interval*2 > now:
            ps.end = now
            db.session.add(ps)
            db.session.commit()
        # Case (2a)
        else:
            # if ps.status != ProbeStatusType.online or ps.status.end <= datetime.utcnow() + interval:
            ps.active = False
            ps.end = now
            db.session.add(ps)
            db.session.commit()

            ps = None

    # Case (1)
    if not ps:
        ps = ProbeStatus(probe_id=probe.id,
                         active=True,
                         status=ProbeStatusType.online,
                         begin=now,
                         end=now+timedelta(milliseconds=1))
        db.session.add(ps)
        db.session.commit()

    # Connect to redis queue and wait for command
    pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(f"probe:{probe.id}")
    # This is because pubsub.listen() does not hava a timeout
    # and get_message consumes the subscribe message as well
    # https://github.com/andymccurdy/redis-py/issues/733
    stoptime = time.time() + app.config["LONG_POLLING_INTERVAL"]
    while time.time() < stoptime:
        msg = pubsub.get_message(timeout=stoptime - time.time())
        if msg:
            return jsonify({'command': msg['data'].decode()})

    return "", 200


@app.route('/probe/system_information', methods=['POST'])
@token_auth.require_token(TokenScope.Probe)
def probe_system_information():
    """
    Endpoint for Uploading ProbeSystemInformation
    """
    if not g.token.probe:
        return "", 403
    probe = g.token.probe[0]

    if not request.json:
        return "", 400

    psi = ProbeSystemInformation(probe_id=probe.id,
                                 timestamp=utils.now(),
                                 information=dumps(request.json))
    db.session.add(psi)
    db.session.commit()

    return "", 200

class ProbeTokenActivationHandler(token_auth.TokenActivationHandler):
    @staticmethod
    def active(scope):
        return TokenScope.Probe in scope

    def __init__(self):
        self.name = None
        self.token = None

    def validate_request(self, request):
        if "name" not in request.values:
            return "name missing", 400

        self.name = request.values["name"]

    def after_token_activation(self, session, token):
        assert self.name != None

        self.token = token
        session.add(Probe(
            name=self.name,
            token=token,
            ))

    def handle_activation_error(self, session, exc):
        assert self.token != None

        if isinstance(exc, sqlexc.IntegrityError):
            duplicate_name = session.scalar(
                    select(Probe)
                    .where((Probe.name == self.name) & (Probe.token_id != self.token.id))
                    )

            if duplicate_name is not None:
                return "Probe name is not unique", 400
