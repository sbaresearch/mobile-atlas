import datetime
import enum
import base64
import json

from typing import Optional, List
from moatt_types.connect import ApduOp
import moatt_types.connect as con_types
from moatt_server.utils import now
from moatt_server.config import MamConfig
from sqlalchemy import (
        String, DateTime, Boolean, Integer, ForeignKey, Text, Enum, LargeBinary, TypeDecorator,
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
    ip: Mapped[str] = mapped_column(Text, unique=True)
    allow_registration: Mapped[bool] = mapped_column(Boolean, default=False)
    token_id: Mapped[int] = mapped_column(
            Integer,
            ForeignKey("mam_tokens.id"),
            unique=True,
            )
    token: Mapped["MamToken"] = relationship(back_populates="config")

@enum.verify(enum.NAMED_FLAGS)
class TokenScope(enum.Flag):
    Wireguard = 1
    Probe = 2
    Both = 3

    def pretty(self, compact=False):
        joiner = " | " if not compact else "|"
        return joiner.join([s.name for s in self]) or "none"

class TokenScopeType(TypeDecorator):
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, _):
        return f"scope:{value.value}"

    def process_result_value(self, value, _):
        return TokenScope(int(value[6:]))

@enum.unique
class TokenAction(enum.Enum):
    Registered = 1
    Activated = 2
    Access = 3
    Deactivated = 4

class MamToken(Base):
    __tablename__ = "mam_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[Optional[str]] = mapped_column(String, index=True, unique=True)
    token_candidate: Mapped[Optional[str]] = mapped_column(String, index=True, unique=True)
    mac: Mapped[str] = mapped_column(Text)
    logs: Mapped[List["MamTokenAccessLog"]] = relationship(back_populates="token", order_by="MamTokenAccessLog.time.desc()")
    scope: Mapped[TokenScope] = mapped_column(TokenScopeType)
    config: Mapped[List[WireguardConfig]] = relationship(back_populates="token", cascade="all, delete")
    probe: Mapped[List["Probe"]] = relationship(back_populates="token", cascade="all, delete")

    def token_value(self):
        if self.token is None:
            return self.token_candidate
        else:
            return self.token

    def activate(self, session):
        if self.token_candidate is not None:
            self.token = self.token_candidate
            self.token_candidate = None

        l = MamTokenAccessLog(
                token_id=self.id,
                token_value=self.token,
                scope=self.scope,
                action=TokenAction.Activated,
                )

        session.add(self)
        session.add(l)

class MamTokenAccessLog(Base):
    __tablename__ = "mam_token_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("mam_tokens.id"))
    token: Mapped[List[MamToken]] = relationship(back_populates="logs")
    token_value: Mapped[str] = mapped_column(String)
    scope: Mapped[TokenScope] = mapped_column(TokenScopeType)
    time: Mapped[datetime.datetime] = mapped_column(TZDateTime, insert_default=now)
    action: Mapped[TokenAction] = mapped_column(Enum(TokenAction, values_callable=lambda x: [f"action:{e.value}" for e in x]))

class WireguardConfigLogs(Base):
    __tablename__ = "wireguard_config_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[Optional[str]] = mapped_column(Text)
    token: Mapped[str] = mapped_column(String)
    publickey: Mapped[str] = mapped_column(Text)
    register_time: Mapped[datetime.datetime] = mapped_column(TZDateTime)
    ip: Mapped[str] = mapped_column(Text)
    successful: Mapped[bool] = mapped_column(Boolean, default=False)

class Probe(Base):
    __tablename__ = "probe"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[List["ProbeStatus"]] = relationship(
            back_populates="probe",
            cascade="all, delete",
            order_by="ProbeStatus.active.desc(), ProbeStatus.begin.desc()",
            )
    token_id: Mapped[int] = mapped_column(
            Integer,
            ForeignKey("mam_tokens.id"),
            unique=True,
            )
    token: Mapped[MamToken] = relationship(back_populates="probe")
    country: Mapped[Optional[str]] = mapped_column(String(2))
    last_poll: Mapped[Optional[datetime.datetime]] = mapped_column(TZDateTime)
    startup_log: Mapped[List["ProbeServiceStartupLog"]] = relationship(
            back_populates="probe",
            cascade="all, delete",
            order_by="ProbeServiceStartupLog.timestamp.desc()",
            )
    system_info: Mapped[List["ProbeSystemInformation"]] = relationship(
            back_populates="probe",
            cascade="all, delete",
            order_by="ProbeSystemInformation.timestamp.desc()",
            )

    def __repr__(self):
        return f"<Probe {self.id}>"

    def to_dict(self):
        return {'id': self.id,
                'name': self.name,
                'mac': self.token.mac}

    def is_polling(self):
        if self.last_poll is None:
            return False

        if self.last_poll + datetime.timedelta(seconds=MamConfig.LONG_POLLING_INTERVAL) \
                <= datetime.datetime.now(tz=datetime.timezone.utc):
            return False
        else:
            return True

    def activation_time(self):
        return next(map(lambda x: x.time, filter(lambda x: x.action == TokenAction.Activated, self.token.logs)), None)

    def time_since_activation(self):
        time = self.activation_time()

        if time is None:
            return ""
        else:
            time = now() - time
            hours, rem = divmod(time.seconds, 3600)
            minutes, seconds = divmod(rem, 60)

            if time.days != 0:
                return f"{time.days}d {hours:02}:{minutes:02}:{seconds:02}"
            else:
                return f"{hours:02}:{minutes:02}:{seconds:02}"

    def get_status_statistics(self):
        """
        Calculate durations and percentages for list of status
        """
        activated = self.activation_time()
        current_time = now()

        if activated is None:
            known_for = datetime.timedelta()
        elif self.status:
            #known_for = (self.status[0].end - self.status[-1].begin) 
            known_for = (self.status[0].end - activated)
        else:
            known_for = current_time - activated

        durations = {st.name: datetime.timedelta() for st in ProbeStatusType}
        for s in self.status:
            durations[s.status.name] += s.duration() # pyright: ignore

        if self.status and activated is not None:
            durations["pre_registration"] = self.status[-1].begin - activated
        elif activated is not None:
            durations["pre_registration"] = current_time - activated

        if known_for > datetime.timedelta():
            percentages = {st: (duration / known_for * 100) for st, duration in durations.items()}
        else:
            percentages = {st: 0 for st, _ in durations.items()}

        return durations, percentages

    def is_activated(self):
        return self.token is not None

class ProbeServiceStartupLog(Base):
    __tablename__ = "probe_service_startup_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime.datetime] = mapped_column(TZDateTime, nullable=False)
    probe_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("probe.id"))
    probe: Mapped[Probe] = relationship(back_populates="startup_log")

class ProbeStatusType(enum.Enum):
    online = "online"
    offline = "offline"

class ProbeStatus(Base):
    __tablename__ = "probe_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    probe_id: Mapped[int] = mapped_column(Integer, ForeignKey("probe.id"))
    probe: Mapped[Probe] = relationship(back_populates="status")
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    status: Mapped[Enum] = mapped_column(Enum(ProbeStatusType), nullable=False)
    begin: Mapped[datetime.datetime] = mapped_column(TZDateTime, nullable=False)
    end: Mapped[datetime.datetime] = mapped_column(TZDateTime)

    def __repr__(self):
        return f"<Probe{self.id}Status {self.status.name} {self.begin}-{self.end} {'[Active]' if self.active else ''} >"

    def duration(self):
        if self.begin and self.end:
            return self.end - self.begin
        else:
            return datetime.timedelta()


class ProbeSystemInformation(Base):
    __tablename__ = "probe_system_information"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    probe_id: Mapped[int] = mapped_column(Integer, ForeignKey('probe.id'))
    probe: Mapped[List[Probe]] = relationship(back_populates="system_info")
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
