from app import app, db, basic_auth, Config
from app.models import WireguardConfig, WireguardConfigAttempt
from flask import request, render_template, jsonify

import base64
import re
from datetime import datetime
import socket
import tempfile
import subprocess


@app.route('/wireguard', methods=['GET'])
@basic_auth.required
def wireguard_index():
    wgs = WireguardConfig.query.all()
    wgas = WireguardConfigAttempt.query.order_by(WireguardConfigAttempt.register_time.desc()).limit(10).all()
    wgas.reverse()
    return render_template("wireguard.html",
                           wgs=wgs,
                           wgas=wgas,
                           config=get_current_wireguard_config(),
                           status=get_current_wireguard_status())


@app.route('/wireguard/register', methods=['POST'])
def wireguard_register():
    """
    Register the public key of a Probe for Wireguard
    Expects arguments "mac" and "publickey"
    """
    if 'mac' not in request.values or 'publickey' not in request.values:
        return "mac/publickey missing", 400

    mac = request.values['mac']
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
        return "mac invalid, use 11:22:33:44:55:66", 400

    publickey = request.values['publickey']
    try:
        if len(base64.decodebytes(publickey.encode())) != 32:
            log_config_attempt(mac)
            return "publickey invalid", 400
    except:
        log_config_attempt(mac)
        return "publickey invalid", 400

    wg = WireguardConfig.query.filter(WireguardConfig.mac == mac).first()

    if not wg:  # If there is non, it cannot be active
        log_config_attempt(mac, publickey)
        return "mac unknown", 403
    else:  # If there is a probe, update
        if not wg.allow_registration:
            log_config_attempt(mac, publickey)
            return "mac not allowed", 403
        else:
            # Update Values
            wg.publickey = publickey
            wireguard_configuration(publickey, wg.ip)
            wg.allow_registration = False
            wg.register_time = datetime.utcnow()

            # Log the successful attempt
            log_config_attempt(mac, publickey, True)
            db.session.add(wg)
            db.session.commit()

            config = dict()
            config['ip'] = wg.ip
            config['endpoint'] = app.config.get("WIREGUARD_ENDPOINT")
            config['endpoint_publickey'] = app.config.get("WIREGUARD_PUBLIC_KEY")
            config['allowed_ips'] = app.config.get("WIREGUARD_ALLOWED_IPS")
            config['dns'] = app.config.get("WIREGUARD_DNS")

            return jsonify(config)


@app.route('/wireguard/allow', methods=['POST'])
@basic_auth.required
def wireguard_allow():
    if 'mac' not in request.values or 'ip' not in request.values:
        return "mac or ip missing", 400

    mac = request.values['mac']
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
        return "mac invalid, use 11:22:33:44:55:66", 400

    ip = request.values['ip']
    try:
        socket.inet_aton(ip)
    except:
        return "ip invalid", 400

    wg = WireguardConfig.query.filter(WireguardConfig.mac == mac).first()

    if not wg:  # If there is non, create
        wg = WireguardConfig(mac=mac, ip=ip, allow_registration=True)
    else:
        wg.ip = ip
        wg.allow_registration = True

    db.session.add(wg)
    db.session.commit()
    return "allowed", 200


@app.route('/wireguard/disallow', methods=['POST'])
@basic_auth.required
def wireguard_disallow():
    if 'mac' not in request.values:
        return "mac missing", 400

    mac = request.values['mac']
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
        return "mac invalid, use 11:22:33:44:55:66", 400

    wg = WireguardConfig.query.filter(WireguardConfig.mac == mac).first()

    if not wg:  # If there is non return 404
        return "mac not found", 404
    else:
        wg.allow_registration = False

    db.session.add(wg)
    db.session.commit()
    return "disallowed", 200


def log_config_attempt(mac, publickey='', successful=False):
    wga = WireguardConfigAttempt(mac=mac,
                                 publickey=publickey,
                                 register_time=datetime.utcnow(),
                                 ip=request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
                                 successful=successful)
    db.session.add(wga)
    db.session.commit()


def wireguard_configuration(publickey, ip):
    """
    Configure Wireguard locally

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg addconf wg0 /tmp/wireguard
    """
    # TODO validate values again, because here it is written to file

    # Start with writing the config to a temprary file
    with open('/tmp/wireguard', 'w') as tf:
        tf.write(f"[Peer]\n")
        tf.write(f"PublicKey = {publickey}\n")
        tf.write(f"AllowedIPs = {ip}/32\n\n")

    subprocess.Popen(f"sudo wg addconf wg0 /tmp/wireguard", shell=True).wait()
    # TODO somehow log the changed configs to return to something different


def get_current_wireguard_config():
    """
    Get the current wireguard config

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg showconf wg0
    """
    try:
        return subprocess.check_output(f"sudo wg showconf wg0 | grep -v PrivateKey", shell=True).decode()
    except subprocess.CalledProcessError as e:
        return e


def get_current_wireguard_status():
    """
    Get the current wireguard status

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg show wg0
    """
    try:
        return subprocess.check_output(f"sudo wg show wg0", shell=True).decode()
    except subprocess.CalledProcessError as e:
        return e
