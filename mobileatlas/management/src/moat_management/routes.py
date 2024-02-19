from flask import render_template, jsonify, request
from sqlalchemy import select
from moatt_server.management import db, app, redis_client, basic_auth
from moatt_server.models import Probe, ProbeServiceStartupLog, ProbeStatus, ProbeStatusType, ProbeSystemInformation, TokenAction
from moatt_server import utils
from datetime import timedelta, datetime, timezone
import pycountry

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
    all_probes = list(db.session.scalars(select(Probe)))
    #startups = {}
    #status = {}
    #psis = {}

    #for probe in all_probes:
        #startups[probe.id] = db.session.scalar(select(ProbeServiceStartupLog).filter_by(mac=probe.token.mac)\
        #    .order_by(ProbeServiceStartupLog.timestamp.desc()))

        #status[probe.id] = db.session.scalar(
        #        select(ProbeStatus)
        #        .where((ProbeStatus.probe_id == probe.id) & (ProbeStatus.active == True))
        #        )
        #psis[probe.id] = db.session.scalar(select(ProbeSystemInformation).filter_by(probe_id=probe.id)\
        #    .order_by(ProbeSystemInformation.timestamp.desc()))

    return render_template(
            "probes.html",
            probes=all_probes,
            #startups=startups,
            #status=status,
            #psis=psis,
            format_country=format_country,
            )


@app.route('/probes/check_status', methods=['GET'])
@basic_auth.required
def status_check():
    """
    Check Status of all probes, and turn to offline or prolongen offline
    This is to be called by a cronjob - See status_check_cron.py
    :return: JSON of newly offline Probes
    """
    #online_statuses = ProbeStatus.query.filter_by(active=True).all()
    online_statuses = db.session.scalars(select(ProbeStatus).filter_by(active=True))
    # When end datetime is due + interval, close active one and create new offline
    interval = timedelta(seconds=app.config["LONG_POLLING_INTERVAL"])
    now = utils.now()

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
                notification.append(ps.probe.to_dict())

        db.session.add(ps)
        db.session.commit()

    return jsonify(notification), 200


@app.route('/probe/<int:id>')
@basic_auth.required
def probe_details(id):
    """
    Show details of probe
    """
    p = db.get_or_404(Probe, id)
    #startups = db.session.scalars(select(ProbeServiceStartupLog).filter_by(mac=p.token.mac).order_by(ProbeServiceStartupLog.timestamp.desc()))
    #status = db.session.scalars(select(ProbeStatus).filter_by(probe_id=p.id).order_by(ProbeStatus.begin.desc()))
    #psi = db.session.scalars(select(ProbeSystemInformation).filter_by(probe_id=p.id).order_by(ProbeSystemInformation.timestamp.desc()))
    _, percentages = p.get_status_statistics()
    return render_template("probe.html", p=p, percentages=percentages, format_country=format_country)


@app.route('/probe/<int:id>/systeminformations')
@basic_auth.required
def probe_systeminformations(id):
    """
    Show all service systeminformations for one probe
    """
    p = db.get_or_404(Probe, id)
    #psi = db.session.scalars(select(ProbeSystemInformation).filter_by(probe_id=p.id).order_by(ProbeSystemInformation.timestamp.desc()))

    return render_template("probe_systeminformations.html", p=p)


@app.route('/probe/<int:id>/startups')
@basic_auth.required
def probe_startups(id):
    """
    Show all service startups for one probe
    """
    p = db.get_or_404(Probe, id)
    #startups = ProbeServiceStartupLog.query.filter_by(mac=p.mac).order_by(ProbeServiceStartupLog.timestamp.desc()).all()
    #startups = db.session.scalars(select(ProbeServiceStartupLog).filter_by(mac=p.token.mac).order_by(ProbeServiceStartupLog.timestamp.desc()))

    return render_template("probe_startups.html", p=p)


@app.route('/probe/<int:id>/status')
@basic_auth.required
def probe_status(id):
    """
    Show all status for one probe
    """
    p = db.get_or_404(Probe, id)
    #status = db.session.scalars(select(ProbeStatus).filter_by(probe_id=p.id).order_by(ProbeStatus.begin.desc()))
    durations, percentages = p.get_status_statistics()

    return render_template(
            "probe_status.html",
            p=p,
            durations=durations,
            percentages=percentages,
            )




@app.route('/probe/<int:id>/change_name/<name>', methods=['POST'])
@basic_auth.required
def change_probe_name(id, name):
    p = db.get_or_404(Probe, id)
    p.name = name
    db.session.add(p)
    db.session.commit()
    return "", 200

@app.route('/probe/<int:id>/change_country', methods=['POST'])
@basic_auth.required
def change_country(id):
    if "country" not in request.values:
        return "missing country", 400

    p = db.get_or_404(Probe, id)
    try:
        country = pycountry.countries.search_fuzzy(request.values['country'])[0]
    except:
        return "found no matching country", 404

    p.country = country.alpha_2
    db.session.commit()

    return "", 200

@app.route('/probe/<int:id>/execute/<command>', methods=['POST'])
@basic_auth.required
def execute_probe(id, command):
    db.get_or_404(Probe, id)
    if command not in ["exit", "system_information", "git_pull"]:
        return "", 400

    redis_client.publish(f"probe:{id}", command)
    return "", 200

@app.template_filter("format_timedelta")
def format_timedelta(td, fmt="{hours:02}:{m:02}:{s:02}"):
    args = {}
    args["weeks"] = td // timedelta(weeks=1)
    args["days"] = td // timedelta(days=1)
    args["hours"] = td // timedelta(hours=1)
    args["minutes"] = td // timedelta(minutes=1)
    args["seconds"] = td // timedelta(seconds=1)
    args["milliseconds"] = td // timedelta(milliseconds=1)
    args["microseconds"] = td // timedelta(microseconds=1)

    args["s"] = args["seconds"] % 60
    args["m"] = args["minutes"] % 60

    return fmt.format(**args)

def format_country(country):
    try:
        country = pycountry.countries.get(alpha_2=country)
    except:
        return "n/a"

    if country is None:
        return "n/a"

    return f"{country.name} {country.flag}"
