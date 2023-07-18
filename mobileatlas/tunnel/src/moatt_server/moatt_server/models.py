import datetime
import enum
import base64
import random
import string
import json

from typing import Optional, List
from moatt_types.connect import ApduOp
import moatt_types.connect as con_types
from moatt_server.utils import now
from sqlalchemy import (
        String, DateTime, Boolean, Integer, ForeignKey, Text, Enum, LargeBinary, TypeDecorator
        )
from sqlalchemy.orm import relationship, DeclarativeBase, mapped_column, Mapped

# https://docs.sqlalchemy.org/en/20/core/custom_types.html#store-timezone-aware-timestamps-as-timezone-naive-utc
class TZDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, _):
        if value is not None:
            if not value.tzinfo:
                raise TypeError("tzinfo is required")
            value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, _):
        if value is not None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value

class Base(DeclarativeBase):
    pass

class Token(Base):
    __tablename__ = "tokens"

    value: Mapped[str] = mapped_column(String(36), primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(TZDateTime)
    expires: Mapped[Optional[datetime.datetime]] = mapped_column(TZDateTime)
    last_access: Mapped[Optional[datetime.datetime]] = mapped_column(TZDateTime)
    active: Mapped[bool] = mapped_column(Boolean)
    sessions: Mapped[List["SessionToken"]] = relationship("SessionToken", back_populates="token")

class SessionToken(Base):
    __tablename__ = "sessiontokens"

    value: Mapped[str] = mapped_column(String(36), primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
            TZDateTime,
            default=datetime.datetime.now(datetime.timezone.utc),
            )
    expires: Mapped[Optional[datetime.datetime]] = mapped_column(TZDateTime)
    last_access: Mapped[datetime.datetime] = mapped_column(
            TZDateTime,
            default=datetime.datetime.now(datetime.timezone.utc),
            )
    token_id: Mapped[str] = mapped_column(String(36), ForeignKey("tokens.value"))
    token: Mapped[Token] = relationship(back_populates="sessions")
    provider: Mapped[Optional["Provider"]] = relationship(back_populates="session_token")

    def to_con_type(self) -> con_types.SessionToken:
        return con_types.SessionToken(base64.b64decode(self.value, validate=True))

class Imsi(Base):
    __tablename__ = "imsis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imsi: Mapped[str] = mapped_column(String)
    registered: Mapped[datetime.datetime] = mapped_column(
            TZDateTime,
            default=datetime.datetime.now(datetime.timezone.utc),
            )
    sim_iccid: Mapped[str] = mapped_column(String, ForeignKey("sims.iccid"))
    sim: Mapped["Sim"] = relationship("Sim", back_populates="imsi")

class Sim(Base):
    __tablename__ = "sims"

    iccid: Mapped[str] = mapped_column(String, primary_key=True)
    imsi: Mapped[List["Imsi"]] = relationship("Imsi", back_populates="sim")
    available: Mapped[bool] = mapped_column(Boolean) # TODO: currently unused
    provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id"))
    provider: Mapped[Optional["Provider"]] = relationship("Provider", back_populates="sims")

class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessiontokens.value"))
    session_token: Mapped[SessionToken] = relationship(back_populates="provider")
    allow_reregistration: Mapped[bool] = mapped_column(Boolean, default=True)

    sims: Mapped[List["Sim"]] = relationship("Sim", back_populates="provider")

#class Probe(Base):
#    __tablename__ = "probes"
#
#    id: Mapped[int] = mapped_column(Integer, primary_key=True)
#    name: Mapped[str] = mapped_column(Text, unique=True)
#    mac: Mapped[str] = mapped_column(Text, index=True, unique=True)
#    token: Mapped[int] = mapped_column(Integer, ForeignKey("tokens.value"))

@enum.unique
class Sender(enum.Enum):
    Probe = 1
    Provider = 2

class ApduLog(Base):
    __tablename__ = "apdu_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
            TZDateTime,
            default=datetime.datetime.now(datetime.timezone.utc),
            )
    sim_id: Mapped[str] = mapped_column(String, ForeignKey("sims.iccid"))
    sim: Mapped[Sim] = relationship("Sim")
    command: Mapped[Enum] = mapped_column(Enum(ApduOp))
    payload: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    sender: Mapped[Enum] = mapped_column(Enum(Sender))

# +----------------+
# |   MAM Tables   |
# +----------------+

class WireguardConfig(Base):
    __tablename__ = "wireguard_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #mac: Mapped[Optional[str]] = mapped_column(Text, index=True, unique=True)
    publickey: Mapped[Optional[str]] = mapped_column(Text, index=True)
    register_time: Mapped[datetime.datetime] = mapped_column(TZDateTime, insert_default=now)
    ip: Mapped[str] = mapped_column(Text)
    allow_registration: Mapped[bool] = mapped_column(Boolean, default=False)
    token_id: Mapped[int] = mapped_column(
            Integer,
            ForeignKey("wireguard_tokens.id"),
            unique=True,
            )
    token: Mapped["WireguardToken"] = relationship(back_populates="config")


class WireguardToken(Base):
    __tablename__ = "wireguard_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[Optional[str]] = mapped_column(String, index=True, unique=True)
    token_candidate: Mapped[Optional[str]] = mapped_column(String, index=True, unique=True)
    mac: Mapped[Optional[str]] = mapped_column(Text)
    created: Mapped[datetime.datetime] = mapped_column(TZDateTime, insert_default=now)
    config: Mapped[List[WireguardConfig]] = relationship(back_populates="token")

    def activate(self, session, ip):
        self.token = self.token_candidate
        self.token_candidate = None

        if len(self.config) == 1:
            self.config[0].ip = ip
            self.config[0].allow_registration = True
        else:
            wgc = WireguardConfig(
                    token=self,
                    ip=ip,
                    allow_registration=True,
                    )
            session.add(wgc)
        session.add(self)

class WireguardConfigLogs(Base):
    __tablename__ = "wireguard_config_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[Optional[str]] = mapped_column(Text)
    token: Mapped[str] = mapped_column(String)
    publickey: Mapped[str] = mapped_column(Text)
    register_time: Mapped[datetime.datetime] = mapped_column(TZDateTime)
    ip: Mapped[str] = mapped_column(Text)
    successful: Mapped[bool] = mapped_column(Boolean, default=False)


class TokenMixin(object):
    token: Mapped[str] = mapped_column(String(32), index=True, unique=True)
    token_candidate: Mapped[str] = mapped_column(String(32), index=True, unique=True)
    token_expiration: Mapped[datetime.datetime] = mapped_column(TZDateTime)
    token_last_access: Mapped[datetime.datetime] = mapped_column(TZDateTime)

    def access(self, session):
        self.token_last_access = datetime.datetime.now(tz=datetime.timezone.utc)
        session.add(self)
        session.commit()

    def is_polling(self):
        if not self.token_last_access:
            return False
        elif self.token_last_access + datetime.timedelta(seconds=60) \
                <= datetime.datetime.now(tz=datetime.timezone.utc): # TODO: use LONG_POLLING_INTERVAL from config
            return False
        else:
            return True

    def generate_token_candidate(self):
        self.token_candidate = ''.join((random.choice(string.digits + string.ascii_letters) for _ in range(32)))
        return self.token_candidate

    def revoke_token(self, session):
        self.token_expiration = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(seconds=1)
        session.add(self)
        session.commit()

    def activate(self, session):
        self.token = self.token_candidate
        self.token_expiration = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(days=365)
        session.add(self)
        session.commit()

    def is_activated(self):
        return False if not self.token_expiration or self.token_expiration < datetime.datetime.now(tz=datetime.timezone.utc) else True

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


class Probe(Base, TokenMixin):
    __tablename__ = "probe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    mac: Mapped[Optional[str]] = mapped_column(Text, index=True, unique=True)
    status: Mapped[Optional["ProbeStatus"]] = relationship(back_populates="probe")

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


class ProbeServiceStartupLog(Base):
    __tablename__ = "probe_service_startup_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[Optional[str]] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(TZDateTime, nullable=False)

class ProbeStatusType(enum.Enum):
    online = "online"
    offline = "offline"

class ProbeStatus(Base):
    __tablename__ = "probe_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    probe_id: Mapped[int] = mapped_column(Integer, ForeignKey("probe.id"), nullable=False) # TODO
    probe: Mapped[Probe] = relationship(back_populates="status")
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    status: Mapped[Enum] = mapped_column(Enum(ProbeStatusType), nullable=False)
    begin: Mapped[datetime.datetime] = mapped_column(TZDateTime, nullable=False)
    end: Mapped[datetime.datetime] = mapped_column(TZDateTime)

    def __repr__(self):
        return f"<Probe{self.id}Status {self.status.name} {self.begin}-{self.end} {'[Active]' if self.active else ''} >"

    def duration(self):
        if self.begin and self.end:
            delta = self.end - self.begin
            return delta - datetime.timedelta(microseconds=delta.microseconds)
        else:
            return datetime.timedelta()


class ProbeSystemInformation(Base):
    __tablename__ = "probe_system_information"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    probe_id: Mapped[int] = mapped_column(Integer, ForeignKey('probe.id'), nullable=False) # TODO
    timestamp: Mapped[datetime.datetime] = mapped_column(TZDateTime, nullable=False)
    information: Mapped[str] = mapped_column(Text(), nullable=False)

    def uptime(self):
        return datetime.timedelta(seconds=round(json.loads(self.information).get("uptime", None)))

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
