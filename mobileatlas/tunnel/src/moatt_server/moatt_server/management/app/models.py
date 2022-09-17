import random
import string
import enum
import json
from datetime import datetime, timedelta

from app import db, app


class WireguardConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.Text, index=True, unique=True)
    publickey = db.Column(db.Text, index=True)
    register_time = db.Column(db.DateTime)
    ip = db.Column(db.Text)
    allow_registration = db.Column(db.Boolean, default=False)


class WireguardConfigAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.Text)
    publickey = db.Column(db.Text)
    register_time = db.Column(db.DateTime)
    ip = db.Column(db.Text)
    successful = db.Column(db.Boolean, default=False)


class TokenMixin(object):
    token = db.Column(db.String(32), index=True, unique=True)
    token_candidate = db.Column(db.String(32), index=True, unique=True)
    token_expiration = db.Column(db.DateTime)
    token_last_access = db.Column(db.DateTime)

    def access(self):
        self.token_last_access = datetime.utcnow()
        db.session.add(self)
        db.session.commit()

    def is_polling(self):
        if not self.token_last_access:
            return False
        elif self.token_last_access + timedelta(seconds=app.config.get("LONG_POLLING_INTERVAL")) <= datetime.utcnow():
            return False
        else:
            return True

    def generate_token_candidate(self):
        self.token_candidate = ''.join((random.choice(string.digits + string.ascii_letters) for _ in range(32)))
        return self.token_candidate

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)
        db.session.add(self)
        db.session.commit()

    def activate(self):
        self.token = self.token_candidate
        self.token_expiration = datetime.utcnow() + timedelta(days=365)
        db.session.add(self)
        db.session.commit()

    def is_activated(self):
        return False if not self.token_expiration or self.token_expiration < datetime.utcnow() else True

    @staticmethod
    def _check_token(token, _class):
        obj = _class.query.filter_by(token=token).first()
        if obj and obj.is_activated():
            return obj
        else:
            return None

    @staticmethod
    def _check_token_candidate(token, _class):
        return _class.query.filter_by(token_candidate=token).first()


class Probe(db.Model, TokenMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, unique=True)
    mac = db.Column(db.Text, index=True, unique=True)

    def __repr__(self):
        return f"<Probe {self.id}>"

    def to_dict(self):
        return {'id': self.id,
                'name': self.name,
                'mac': self.mac}

    @staticmethod
    def check_token(token):
        # noinspection PyTypeChecker
        return TokenMixin._check_token(token, Probe)

    @staticmethod
    def check_token_candidate(token):
        # noinspection PyTypeChecker
        return TokenMixin._check_token_candidate(token, Probe)


class ProbeServiceStartupLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    mac = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)


class ProbeStatusType(enum.Enum):
    online = "online"
    offline = "offline"


class ProbeStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    probe_id = db.Column(db.Integer, db.ForeignKey('probe.id'), nullable=False)
    active = db.Column(db.Boolean, index=True)
    status = db.Column(db.Enum(ProbeStatusType), nullable=False)
    begin = db.Column(db.DateTime, nullable=False)
    end = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Probe{self.id}Status {self.status.name} {self.begin}-{self.end} {'[Active]' if self.active else ''} >"

    def duration(self):
        if self.begin and self.end:
            delta = self.end - self.begin
            return delta-timedelta(microseconds=delta.microseconds)
        else:
            return timedelta()


class ProbeSystemInformation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    probe_id = db.Column(db.Integer, db.ForeignKey('probe.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    information = db.Column(db.Text(), nullable=False)

    def uptime(self):
        return timedelta(seconds=round(json.loads(self.information).get("uptime", None)))

    def temperature(self):
        return json.loads(self.information).get("temp", None)

    def head(self):
        return json.loads(self.information).get("head", None)

    def pretty(self):
        return json.dumps(json.loads(self.information), sort_keys=True, indent=4)

    def network(self):
        network = json.loads(self.information).get("network")
        try:
            return [(dev["ifname"],
                     dev["addr_info"][0]["local"],
                     dev["stats64"]["rx"]["bytes"]/1000000,
                     dev["stats64"]["tx"]["bytes"]/1000000) for dev in network]
        except Exception:
            return None
