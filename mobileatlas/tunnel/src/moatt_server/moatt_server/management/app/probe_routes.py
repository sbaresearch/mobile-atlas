from flask import jsonify, request
from app import app, redis_client
from app.models import Probe, ProbeServiceStartupLog, ProbeStatus, ProbeStatusType, ProbeSystemInformation
from app import db, token_auth
from datetime import datetime, timedelta
from json import dumps
import time
import re

"""
Endpoints called from the Measurement Probe are listed in this file
"""


@app.route('/probe/startup', methods=['POST'])
@app.route('/probe/reboot', methods=['POST'])  # TODO delete me after client update
def startup_log():
    """
    Unauthenticated startup log
    Example command to execute:
        curl --request POST --data "mac=`cat /sys/class/net/eth0/address`"  MAM/probe/startup
    """
    # Check if mac is valid  # todo deduplicate *mac
    if 'mac' not in request.values:
        return "", 400
    mac = request.values['mac']
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
        return "", 400

    # Check if mac is known in Probe List, otherwise deny
    query = db.session.query(Probe.mac.distinct().label("mac"))
    macs = [row.mac for row in query.all()]

    if mac not in macs:
        return "", 400

    # Create a log entry
    prl = ProbeServiceStartupLog(mac=mac, timestamp=datetime.utcnow())
    db.session.add(prl)
    db.session.commit()

    return "", 200


@app.route('/probe/register', methods=['POST'])
def register_probe():
    """
    Register a probe and do the token stuff
    1a) Token included and authenticated -> Return Probe+Token
    1b) Token included and still Token Candidate -> Return Probe+Token Candidate
    2) Token not included or nonsense -> Generate new Token Candidate -> Return Probe+Token Candidate
    """
    # Case (1)
    token = token_auth.get_token(request)
    if token:
        # Case (1a)
        probe = Probe.check_token(token)
        if probe:
            pd = probe.to_dict()
            pd['token'] = token
            return jsonify(pd), 200

        # Case (1b)
        probe = Probe.check_token_candidate(token)
        if probe:
            pd = probe.to_dict()
            pd['token_candidate'] = token
            return jsonify(pd), 200

    # Case (2)

    # Check if mac is valid  # todo deduplicate *mac
    if 'mac' not in request.values:
        return "", 400
    mac = request.values['mac']
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
        return "mac invalid", 400

    probe = Probe.query.filter(Probe.mac == mac).first()

    if probe:  # If there is a probe, update
        token_candidate = probe.generate_token_candidate()
    else:  # If there is non, create a new
        probe = Probe()
        probe.mac = mac
        token_candidate = probe.generate_token_candidate()

    db.session.add(probe)
    db.session.commit()

    pd = probe.to_dict()
    pd['token_candidate'] = token_candidate

    return jsonify(pd)


@app.route('/probe/poll', methods=['POST'])
def probe_poll():
    """
    The long poll endpoint for the probe
    """
    token = token_auth.get_token(request)  # todo deduplicate *token
    if not token:
        return "", 403

    probe = Probe.check_token(token)
    if not probe:
        return "", 403

    # Mark the Proben Token last access
    probe.access()

    # Include a status update
    #
    # (1) No last status - create a new status
    # (2) Got last status
    #     (2a) Expired - Finish old status - create new status
    #     (2b) Active - Prolong active status
    # Todo move this functionality
    ps = ProbeStatus.query.filter_by(probe_id=probe.id, active=True).first()
    interval = timedelta(seconds=app.config.get("LONG_POLLING_INTERVAL"))
    now = datetime.utcnow()

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
    stoptime = time.time() + app.config.get("LONG_POLLING_INTERVAL")
    while time.time() < stoptime:
        msg = pubsub.get_message(timeout=stoptime - time.time())
        if msg:
            return jsonify({'command': msg['data'].decode()})

    return "", 200


@app.route('/probe/system_information', methods=['POST'])
def probe_system_information():
    """
    Endpoint for Uploading ProbeSystemInformation
    """
    token = token_auth.get_token(request)  # todo deduplicate *token
    if not token:
        return "", 403

    probe = Probe.check_token(token)
    if not probe:
        return "", 403

    if not request.json:
        return "", 400

    psi = ProbeSystemInformation(probe_id=probe.id,
                                 timestamp=datetime.utcnow(),
                                 information=dumps(request.json))
    db.session.add(psi)
    db.session.commit()

    return "", 200
