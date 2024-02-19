from moatt_server.management import app, db, basic_auth
from moatt_server.models import (WireguardConfig, WireguardConfigLogs, MamToken,
                                 TokenScope)
from moatt_server.utils import now
from flask import request, render_template, jsonify, g
from sqlalchemy import select, exc as sqlexc
from moatt_server.management.token_auth import require_token, TokenActivationHandler

import base64
import re
#from datetime import datetime
import socket
import subprocess


@app.route('/wireguard', methods=['GET'])
@basic_auth.required
def wireguard_index():
    wgs = db.session.scalars(select(WireguardConfig)).all()
    wgas = list(db.session.scalars(select(WireguardConfigLogs).order_by(WireguardConfigLogs.register_time.desc()).limit(10)))
    wgas.reverse()
    #active_tokens = db.session.scalars(select(MamToken).where(MamToken.token != None))
    token_reqs = db.session.scalars(select(MamToken).where(MamToken.token == None))
    #token_reqs = list(token_reqs)
    #print(token_reqs[0].token)
    return render_template("wireguard.html",
                           wgs=wgs,
                           wgas=wgas,
                           #active_tokens=active_tokens,
                           token_reqs=token_reqs,
                           config=get_current_wireguard_config(),
                           status=get_current_wireguard_status())

@app.route('/wireguard/register', methods=['POST'])
@require_token(TokenScope.Wireguard)
def wireguard_register():
    """
    Register the public key of a Probe for Wireguard
    Expects arguments "mac" and "publickey"
    """
    if 'publickey' not in request.values or 'mac' not in request.values:
        return "publickey/mac missing", 400

    token = g.token.token
    assert token is not None

    mac = request.values['mac']
    if not re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower()):
        log_config_attempt(g.token.token)
        return "mac invalid, use 11:22:33:44:55:66", 400


    publickey = request.values['publickey']
    try:
        if not publickey.isascii() or len(base64.b64decode(publickey)) != 32:
            log_config_attempt(token, mac=mac)
            return "publickey invalid", 400
    except:
        log_config_attempt(token, mac=mac)
        return "publickey invalid", 400

    wg = g.token.config

    if len(wg) != 1:
        # This should not happen: If wgtoken is active (wgtoken.token is not None)
        # then it should have a corresponding WireguardConfig
        log_config_attempt(token, publickey, mac=mac)
        db.session.delete(g.token)
        db.session.commit()
        return "token invalid", 403
    else:  # If there is a probe, update
        wg = wg[0]
        if not wg.allow_registration:
            log_config_attempt(token, publickey, mac=mac)
            return "registration not allowed", 403
        else:
            # Update Values
            wg.publickey = publickey
            wireguard_configuration(publickey, wg.ip)
            wg.allow_registration = False
            wg.register_time = now()

            if g.token.mac is None:
                g.token.mac = mac

            # Log the successful attempt
            log_config_attempt(token, publickey, True, mac=mac)
            db.session.add(wg)
            db.session.commit()

            config = dict()
            config['ip'] = wg.ip
            config['endpoint'] = app.config.get("WIREGUARD_ENDPOINT")
            config['endpoint_publickey'] = app.config.get("WIREGUARD_PUBLIC_KEY")
            config['allowed_ips'] = app.config.get("WIREGUARD_ALLOWED_IPS")
            config['dns'] = app.config.get("WIREGUARD_DNS")

            return jsonify(config)

def log_config_attempt(token, publickey='', successful=False, mac=None):
    wga = WireguardConfigLogs(token=token,
                                 mac=mac,
                                 publickey=publickey,
                                 register_time=now(),
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
    try:
        if not publickey.isascii() or len(base64.b64decode(publickey)) != 32:
            raise Exception
        # use inet_ntoa to get rid of abbreviated addresses
        # e.g. '127.1'
        ip = socket.inet_ntoa(socket.inet_aton(ip))
    except:
        raise Exception("invalid publickey")

    # Start with writing the config to a temprary file
    with open('/dev/tty', 'w') as tf:
        tf.write(f"[Peer]\n")
        tf.write(f"PublicKey = {publickey}\n")
        tf.write(f"AllowedIPs = {ip}/32\n\n")

    #subprocess.Popen(f"sudo wg addconf wg0 /tmp/wireguard", shell=True).wait()
    # TODO somehow log the changed configs to return to something different


def get_current_wireguard_config():
    """
    Get the current wireguard config

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg showconf wg0
    """
    try:
        #return subprocess.check_output(f"sudo wg showconf wg0 | grep -v PrivateKey", shell=True).decode()
        return subprocess.check_output(f"echo 'todo'", shell=True).decode()
    except subprocess.CalledProcessError as e:
        return e


def get_current_wireguard_status():
    """
    Get the current wireguard status

    Check that python user is enabled in /etc/suders.d/wireguard
    > user ALL = (root) NOPASSWD: /usr/bin/wg show wg0
    """
    try:
        #return subprocess.check_output(f"sudo wg show wg0", shell=True).decode()
        return subprocess.check_output(f"echo 'todo'", shell=True).decode()
    except subprocess.CalledProcessError as e:
        return e

class WgTokenActivationHandler(TokenActivationHandler):
    @staticmethod
    def active(scope):
        return TokenScope.Wireguard in scope

    def __init__(self):
        self.ip = None
        self.token = None

    def validate_request(self, request):
        if "ip" not in request.values:
            return "ip missing", 400

        ip = request.values["ip"]
        try:
            # use inet_ntoa to get the canonical address representation
            # e.g. `127.0.0.1` instead of `127.1`
            self.ip = socket.inet_ntoa(socket.inet_aton(ip))
        except:
            return "ip invalid", 400

    def after_token_activation(self, session, token):
        assert self.ip is not None

        self.token = token

        if len(token.config) == 1:
            token.config[0].ip = self.ip
            token.config[0].allow_registration = True
        else:
            wgc = WireguardConfig(
                    token=token,
                    ip=self.ip,
                    allow_registration=True,
                    )
            session.add(wgc)
        session.add(token)

    def handle_activation_error(self, session, exc):
        assert self.token is not None

        if isinstance(exc, sqlexc.IntegrityError):
            duplicate_ip = session.scalar(
                    select(WireguardConfig)
                    .where((WireguardConfig.ip == self.ip) & (WireguardConfig.token_id != self.token.id))
                    )
            if duplicate_ip is not None:
                return "ip is not unique", 400
