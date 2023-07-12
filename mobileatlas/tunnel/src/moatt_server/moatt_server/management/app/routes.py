from flask import render_template, jsonify
from app import db, app, redis_client, basic_auth
from app.models import Probe, ProbeServiceStartupLog, ProbeStatus, ProbeStatusType, ProbeSystemInformation
from datetime import timedelta, datetime


@app.route('/')
@basic_auth.required
def index():
    """
    Show no content ... only base
    """
    return render_template("index.html")


@app.route('/probes')
@basic_auth.required
def probes():
    """
    Show all probes
    """
    all_probes = Probe.query.all()
    startups = {}
    status = {}
    psis = {}
    for probe in all_probes:
        startups[probe.id] = ProbeServiceStartupLog.query.filter_by(mac=probe.mac)\
            .order_by(ProbeServiceStartupLog.timestamp.desc()).first()
        status[probe.id] = ProbeStatus.query.filter_by(probe_id=probe.id, active=True).first()
        psis[probe.id] = ProbeSystemInformation.query.filter_by(probe_id=probe.id)\
            .order_by(ProbeSystemInformation.timestamp.desc()).first()
    return render_template("probes.html", probes=all_probes, startups=startups, status=status, psis=psis)


@app.route('/probes/check_status', methods=['GET'])
@basic_auth.required
def status_check():
    """
    Check Status of all probes, and turn to offline or prolongen offline
    This is to be called by a cronjob - See status_check_cron.py
    :return: JSON of newly offline Probes
    """
    online_statuses = ProbeStatus.query.filter_by(active=True).all()
    # When end datetime is due + interval, close active one and create new offline
    interval = timedelta(seconds=app.config.get("LONG_POLLING_INTERVAL"))
    now = datetime.utcnow()

    offline_for = timedelta(minutes=30)
    notification = []

    for ps in online_statuses:
        if ps.status == ProbeStatusType.online and ps.end + interval < now:
            ps.active = False
            ps_offline = ProbeStatus(probe_id=ps.probe_id,
                                     active=True,
                                     status=ProbeStatusType.offline,
                                     begin=ps.end,
                                     end=ps.end+timedelta(milliseconds=1))
            db.session.add(ps_offline)
        elif ps.status == ProbeStatusType.offline:
            offline_duration_before = ps.duration()
            ps.end = now
            offline_duration_after = ps.duration()
            if offline_duration_before < offline_for <= offline_duration_after:
                notification.append(Probe.query.filter_by(id=ps.probe_id).first().to_dict())

        db.session.add(ps)
        db.session.commit()

    return jsonify(notification), 200


@app.route('/probe/<int:id>')
@basic_auth.required
def probe_details(id):
    """
    Show details of probe
    """
    p = Probe.query.get_or_404(id)
    startups = ProbeServiceStartupLog.query.filter_by(mac=p.mac).order_by(ProbeServiceStartupLog.timestamp.desc()).all()
    status = ProbeStatus.query.filter_by(probe_id=p.id).order_by(ProbeStatus.begin.desc()).all()
    psi = ProbeSystemInformation.query.filter_by(probe_id=p.id).order_by(ProbeSystemInformation.timestamp.desc()).all()
    _, percentages = get_status_statistics(status)
    return render_template("probe.html", p=p, startups=startups, status=status, percentages=percentages, psi=psi)


@app.route('/probe/<int:id>/systeminformations')
@basic_auth.required
def probe_systeminformations(id):
    """
    Show all service systeminformations for one probe
    """
    p = Probe.query.get_or_404(id)
    psi = ProbeSystemInformation.query.filter_by(probe_id=p.id).order_by(ProbeSystemInformation.timestamp.desc()).all()

    return render_template("probe_systeminformations.html", p=p, psi=psi)


@app.route('/probe/<int:id>/startups')
@basic_auth.required
def probe_startups(id):
    """
    Show all service startups for one probe
    """
    p = Probe.query.get_or_404(id)
    startups = ProbeServiceStartupLog.query.filter_by(mac=p.mac).order_by(ProbeServiceStartupLog.timestamp.desc()).all()

    return render_template("probe_startups.html", p=p, startups=startups)


@app.route('/probe/<int:id>/status')
@basic_auth.required
def probe_status(id):
    """
    Show all status for one probe
    """
    p = Probe.query.get_or_404(id)
    status = ProbeStatus.query.filter_by(probe_id=p.id).order_by(ProbeStatus.begin.desc()).all()
    durations, percentages = get_status_statistics(status)

    return render_template("probe_status.html", p=p, status=status, durations=durations, percentages=percentages)


def get_status_statistics(status):
    """
    Calculate durations and percentages for list of status
    """
    known_for = (status[0].end - status[-1].begin) if status else timedelta(milliseconds=1)
    durations = {st: timedelta() for st in ProbeStatusType}
    for s in status:
        durations[s.status] += s.duration()
    percentages = {st: (duration / known_for * 100) for st, duration in durations.items()}
    return durations, percentages


@app.route('/probe/<int:id>/activate', methods=['POST'])
@basic_auth.required
def activate_probe(id):
    p = Probe.query.get_or_404(id)
    p.activate()
    return "", 200


@app.route('/probe/<int:id>/deactivate', methods=['POST'])
@basic_auth.required
def deactivate_probe(id):
    p = Probe.query.get_or_404(id)
    p.revoke_token()
    return "", 200


@app.route('/probe/<int:id>/change_name/<name>', methods=['POST'])
@basic_auth.required
def change_probe_name(id, name):
    p = Probe.query.get_or_404(id)
    p.name = name
    db.session.add(p)
    db.session.commit()
    return "", 200


@app.route('/probe/<int:id>/execute/<command>', methods=['POST'])
@basic_auth.required
def execute_probe(id, command):
    Probe.query.get_or_404(id)
    if command not in ["exit", "system_information", "git_pull"]:
        return "", 400

    redis_client.publish(f"probe:{id}", command)

    return "", 200
