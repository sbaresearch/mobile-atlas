import datetime
import enum
import base64

from typing import Optional, List
from moatt_types.connect import ApduOp
import moatt_types.connect as con_types
from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Text, Enum, LargeBinary
from sqlalchemy.orm import relationship, DeclarativeBase, mapped_column, Mapped

class Base(DeclarativeBase):
    pass

class Token(Base):
    __tablename__ = "tokens"

    value: Mapped[str] = mapped_column(String(36), primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(DateTime)
    expires: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    last_access: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    active: Mapped[bool] = mapped_column(Boolean)
    sessions: Mapped[List["SessionToken"]] = relationship("SessionToken", back_populates="token")

class SessionToken(Base):
    __tablename__ = "sessiontokens"

    value: Mapped[str] = mapped_column(String(36), primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(DateTime)
    expires: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime)
    last_access: Mapped[datetime.datetime] = mapped_column(DateTime)
    token_id: Mapped[str] = mapped_column(String(36), ForeignKey("tokens.value"))
    token: Mapped[Token] = relationship(back_populates="sessions")
    provider: Mapped[Optional["Provider"]] = relationship(back_populates="session_token")

    def to_con_type(self) -> con_types.SessionToken:
        return con_types.SessionToken(base64.b64decode(self.value, validate=True))

class Imsi(Base):
    __tablename__ = "imsis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    imsi: Mapped[str] = mapped_column(String)
    registered: Mapped[datetime.datetime] = mapped_column(DateTime)
    sim_iccid: Mapped[str] = mapped_column(String, ForeignKey("sims.iccid"))
    sim: Mapped["Sim"] = relationship("Sim", back_populates="imsi")

class Sim(Base):
    __tablename__ = "sims"

    iccid: Mapped[str] = mapped_column(String, primary_key=True)
    imsi: Mapped[List["Imsi"]] = relationship("Imsi", back_populates="sim")
    available: Mapped[bool] = mapped_column(Boolean) # TODO: currently unused
    provider_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("providers.id"))
    provider: Mapped["Provider"] = relationship("Provider", back_populates="sims")

class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_token_id: Mapped[str] = mapped_column(String(36), ForeignKey("sessiontokens.value"))
    session_token: Mapped[SessionToken] = relationship(back_populates="provider")
    allow_reregistration: Mapped[bool] = mapped_column(Boolean, default=True)

    sims: Mapped[List["Sim"]] = relationship("Sim", back_populates="provider")

class Probe(Base):
    __tablename__ = "probes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True)
    mac: Mapped[str] = mapped_column(Text, index=True, unique=True)
    token: Mapped[int] = mapped_column(Integer, ForeignKey("tokens.value"))

@enum.unique
class Sender(enum.Enum):
    Probe = 1
    Provider = 2

class ApduLog(Base):
    __tablename__ = "apdu_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    sim_id: Mapped[str] = mapped_column(String, ForeignKey("sims.iccid"))
    sim: Mapped[Sim] = relationship("Sim")
    command: Mapped[Enum] = mapped_column(Enum(ApduOp))
    payload: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    sender: Mapped[Enum] = mapped_column(Enum(Sender))
