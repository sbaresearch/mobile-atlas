import base64
import enum
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from .config import get_config

LOGGER = logging.getLogger(__name__)


JsonValue = list["JsonValue"] | dict[str, "JsonValue"] | str | bool | int | float | None


class Base(AsyncAttrs, DeclarativeBase):
    pass


class WireguardConfig(Base):
    __tablename__ = "wireguard_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    publickey: Mapped[Optional[str]] = mapped_column(Text, index=True)
    register_time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    ip: Mapped[str] = mapped_column(Text, unique=True)
    allow_registration: Mapped[bool] = mapped_column(Boolean, server_default="FALSE")
    token_id: Mapped[int] = mapped_column(
        ForeignKey("mam_tokens.id"),
        unique=True,
    )
    token: Mapped["MamToken"] = relationship(back_populates="config")


@enum.verify(enum.NAMED_FLAGS)
class TokenScope(int, enum.Flag):
    Wireguard = 1
    Probe = 2
    Both = 3

    def pretty(self, compact=False):
        joiner = " | " if not compact else "|"
        return joiner.join([s.name for s in self]) or "none"


class TokenScopeType(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        return f"scope:{value.value}"

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return TokenScope(int(value.removeprefix("scope:")))


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
    token_candidate: Mapped[Optional[str]] = mapped_column(
        String, index=True, unique=True
    )
    mac: Mapped[Optional[str]] = mapped_column(Text)
    logs: Mapped[List["MamTokenAccessLog"]] = relationship(
        back_populates="token", order_by="MamTokenAccessLog.time.desc()"
    )
    scope: Mapped[TokenScope] = mapped_column(TokenScopeType)
    config: Mapped[Optional[WireguardConfig]] = relationship(
        back_populates="token", cascade="all, delete"
    )
    probe: Mapped[Optional["Probe"]] = relationship(
        back_populates="token", cascade="all, delete"
    )

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
    token_id: Mapped[Optional[int]] = mapped_column(ForeignKey("mam_tokens.id"))
    token: Mapped[List[MamToken]] = relationship(back_populates="logs")
    token_value: Mapped[str] = mapped_column(String)
    scope: Mapped[TokenScope] = mapped_column(TokenScopeType)
    time: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )
    action: Mapped[TokenAction] = mapped_column(
        Enum(TokenAction, values_callable=lambda x: [f"action:{e.value}" for e in x])
    )


class WireguardConfigLogs(Base):
    __tablename__ = "wireguard_config_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[Optional[str]] = mapped_column(Text)
    token: Mapped[str] = mapped_column(String)
    publickey: Mapped[str] = mapped_column(Text)
    register_time: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    ip: Mapped[Optional[str]] = mapped_column(Text)
    successful: Mapped[bool] = mapped_column(Boolean, default=False)


class Probe(Base):
    __tablename__ = "probe"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[List["ProbeStatus"]] = relationship(
        back_populates="probe",
        cascade="all, delete",
        order_by="ProbeStatus.active.desc(), ProbeStatus.begin.desc()",
    )
    token_id: Mapped[int] = mapped_column(
        ForeignKey("mam_tokens.id"),
        unique=True,
    )
    token: Mapped[MamToken] = relationship(back_populates="probe")
    country: Mapped[Optional[str]] = mapped_column(String(2))
    last_poll: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True))
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
        return {"id": self.id, "name": self.name, "mac": self.token.mac}

    def is_polling(self):
        if self.last_poll is None:
            return False

        if self.last_poll + get_config().LONG_POLLING_INTERVAL <= datetime.now(
            tz=timezone.utc
        ):
            return False
        else:
            return True

    def activation_time(self):
        return next(
            map(
                lambda x: x.time,
                filter(lambda x: x.action == TokenAction.Activated, self.token.logs),
            ),
            None,
        )

    def time_since_activation(self):
        time = self.activation_time()

        if time is None:
            return ""
        else:
            time = datetime.now(tz=timezone.utc) - time
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
        current_time = datetime.now(tz=timezone.utc)

        if activated is None:
            known_for = timedelta()
        elif self.status:
            known_for = self.status[0].end - activated
        else:
            known_for = current_time - activated

        durations = {st.name: timedelta() for st in ProbeStatusType}
        for s in self.status:
            durations[s.status.name] += s.duration()  # pyright: ignore

        if self.status and activated is not None:
            durations["pre_registration"] = self.status[-1].begin - activated
        elif activated is not None:
            durations["pre_registration"] = current_time - activated

        if known_for > timedelta():
            percentages = {
                st: (duration / known_for * 100) for st, duration in durations.items()
            }
        else:
            percentages = {st: 0 for st, _ in durations.items()}

        return durations, percentages

    def is_activated(self):
        return self.token is not None


class ProbeServiceStartupLog(Base):
    __tablename__ = "probe_service_startup_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mac: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    probe_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("probe.id"))
    probe: Mapped[Probe] = relationship(back_populates="startup_log")


class ProbeStatusType(enum.Enum):
    online = "online"
    offline = "offline"


class ProbeStatus(Base):
    __tablename__ = "probe_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    probe_id: Mapped[UUID] = mapped_column(ForeignKey("probe.id"))
    probe: Mapped[Probe] = relationship(back_populates="status")
    active: Mapped[bool] = mapped_column(Boolean, index=True)
    status: Mapped[Enum] = mapped_column(Enum(ProbeStatusType), nullable=False)
    begin: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    end: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))

    def __repr__(self):
        return f"<Probe{self.id}Status {self.status.name} {self.begin}-{self.end} {'[Active]' if self.active else ''} >"

    def duration(self):
        if self.begin and self.end:
            return self.end - self.begin
        else:
            return timedelta()


class ProbeSystemInformation(Base):
    __tablename__ = "probe_system_information"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    probe_id: Mapped[UUID] = mapped_column(ForeignKey("probe.id"))
    probe: Mapped[List[Probe]] = relationship(back_populates="system_info")
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    information: Mapped[JsonValue] = mapped_column(JSONB)

    def uptime(self) -> timedelta | None:
        if not isinstance(self.information, dict):
            return None

        up = self.information.get("uptime")
        if isinstance(up, int | float):
            return timedelta(seconds=round(up))
        else:
            return None

    def temperature(self) -> int | float | None:
        if not isinstance(self.information, dict):
            return None

        temp = self.information.get("temp")
        if isinstance(temp, int | float):
            return temp
        else:
            return None

    def head(self) -> str | None:
        if not isinstance(self.information, dict):
            return None

        head = self.information.get("head")
        if isinstance(head, str):
            return head
        else:
            return None

    def pretty(self):
        return json.dumps(self.information, sort_keys=True, indent=4)

    def network(self) -> list[tuple]:
        if not isinstance(self.information, dict):
            return []

        network = self.information.get("network")
        if isinstance(network, list):
            try:
                return [
                    (
                        dev["ifname"],  # type: ignore
                        dev["addr_info"][0]["local"],  # type: ignore
                        dev["stats64"]["rx"]["bytes"] / 1000000,  # type: ignore
                        dev["stats64"]["tx"]["bytes"] / 1000000,
                    )
                    for dev in network
                ]  # type: ignore
            except Exception:
                LOGGER.exception("Failed to retrieve all network information.")
                return []
        else:
            return []


#####################
# SIM-Tunnel models #
#####################


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )


class MoAtTokenScope(int, enum.Flag):
    Probe = 1
    Provider = 2


class MoAtTokenScopeType(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        return f"tunnel-scope:{value.value}"

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return MoAtTokenScope(int(value.removeprefix("tunnel-scope:")))


class TokenSimAssociation(Base):
    __tablename__ = "token_sim_association_table"

    sim_id: Mapped[int] = mapped_column(ForeignKey("sims.id"), primary_key=True)
    token_id: Mapped[int] = mapped_column(
        ForeignKey("moat_tokens.id"), primary_key=True
    )
    provide: Mapped[bool] = mapped_column(server_default="FALSE")
    request: Mapped[bool] = mapped_column(server_default="FALSE")

    token: Mapped["MoAtToken"] = relationship(back_populates="sim_assoc")
    sim: Mapped["Sim"] = relationship(back_populates="token_assoc")


class MoAtToken(Base):
    __tablename__ = "moat_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[bytes] = mapped_column(unique=True)
    allowed_scope: Mapped[MoAtTokenScope] = mapped_column(MoAtTokenScopeType)
    expires: Mapped[Optional[datetime]]
    admin: Mapped[bool] = mapped_column(server_default="FALSE")

    sim_assoc: Mapped[List[TokenSimAssociation]] = relationship(back_populates="token")
    session_tokens: Mapped[List["SessionToken"]] = relationship(back_populates="token")

    def expired(self) -> bool:
        return self.expires is not None and datetime.now(tz=timezone.utc) > self.expires

    def base64_value(self) -> str:
        return base64.b64encode(self.value).decode()


class Sim(Base):
    __tablename__ = "sims"

    id: Mapped[int] = mapped_column(primary_key=True)
    iccid: Mapped[Optional[str]] = mapped_column(unique=True)
    imsi: Mapped[Optional[str]] = mapped_column(unique=True)
    public: Mapped[bool] = mapped_column(server_default="FALSE")

    token_assoc: Mapped[List[TokenSimAssociation]] = relationship(back_populates="sim")


class SessionToken(Base):
    __tablename__ = "moat_session_tokens"
    __table_args__ = (
        CheckConstraint(
            "(probe_id is null) <> (provider_id is null)", name="single_client"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    value: Mapped[bytes] = mapped_column(unique=True)
    token_id: Mapped[int] = mapped_column(ForeignKey("moat_tokens.id"))
    scope: Mapped[MoAtTokenScope] = mapped_column(MoAtTokenScopeType)

    probe_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("probe.id"))
    provider_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("providers.id"))

    token: Mapped[MoAtToken] = relationship(back_populates="session_tokens")
