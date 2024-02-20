import base64
import datetime
import enum
from typing import List, Optional

import moatt_types.connect as con_types
from moatt_types.connect import ApduOp
from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Token(Base):
    __tablename__ = "tokens"

    value: Mapped[str] = mapped_column(String(36), primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True))
    expires: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    last_access: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    active: Mapped[bool]
    sessions: Mapped[List["SessionToken"]] = relationship(
        "SessionToken", back_populates="token"
    )

    def is_valid(self):
        return self.active and not self.is_expired()

    def is_expired(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        return self.expires is not None and self.expires < now


class SessionToken(Base):
    __tablename__ = "sessiontokens"

    value: Mapped[str] = mapped_column(String(36), primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )

    expires: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP(timezone=True)
    )
    last_access: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    token_id: Mapped[str] = mapped_column(String(36), ForeignKey("tokens.value"))
    token: Mapped[Token] = relationship(back_populates="sessions")
    provider: Mapped[Optional["Provider"]] = relationship(
        back_populates="session_token"
    )

    def to_con_type(self) -> con_types.SessionToken:
        return con_types.SessionToken(base64.b64decode(self.value, validate=True))

    def is_valid(self):
        return self.token.is_valid() and not self.is_expired()

    def is_expired(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        return self.expires is not None and self.expires < now


class Imsi(Base):
    __tablename__ = "imsis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imsi: Mapped[str] = mapped_column(String(20))
    registered: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    sim_iccid: Mapped[str] = mapped_column(String(20), ForeignKey("sims.iccid"))
    sim: Mapped["Sim"] = relationship("Sim", back_populates="imsi")


class Sim(Base):
    __tablename__ = "sims"

    iccid: Mapped[str] = mapped_column(String(20), primary_key=True)
    imsi: Mapped[List["Imsi"]] = relationship("Imsi", back_populates="sim")
    in_use: Mapped[bool] = mapped_column(server_default="FALSE")
    provider_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("providers.id")
    )
    provider: Mapped[Optional["Provider"]] = relationship(
        "Provider", back_populates="sims"
    )


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessiontokens.value")
    )
    session_token: Mapped[SessionToken] = relationship(back_populates="provider")
    allow_reregistration: Mapped[bool] = mapped_column(Boolean, server_default="TRUE")
    available: Mapped[int] = mapped_column(server_default="0")

    sims: Mapped[List["Sim"]] = relationship("Sim", back_populates="provider")


class Probe(Base):
    __tablename__ = "probes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    mac: Mapped[str] = mapped_column(Text, index=True, unique=True)
    token: Mapped[str] = mapped_column(ForeignKey("tokens.value"))


@enum.unique
class Sender(enum.Enum):
    Probe = 1
    Provider = 2


class ApduLog(Base):
    __tablename__ = "apdu_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
    )
    sim_id: Mapped[str] = mapped_column(String(20), ForeignKey("sims.iccid"))
    sim: Mapped[Sim] = relationship("Sim")
    command: Mapped[ApduOp]
    payload: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    sender: Mapped[Sender]
