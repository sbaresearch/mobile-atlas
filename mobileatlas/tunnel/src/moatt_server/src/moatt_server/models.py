import datetime
import enum
from typing import List, Optional
from uuid import UUID

from moatt_types.connect import ApduOp
from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Integer, LargeBinary, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Sim(Base):
    __tablename__ = "sims"

    id: Mapped[int] = mapped_column(primary_key=True)
    iccid: Mapped[Optional[str]] = mapped_column(unique=True)
    imsi: Mapped[Optional[str]] = mapped_column(unique=True)
    in_use: Mapped[bool] = mapped_column(server_default="FALSE")
    provider_id: Mapped[UUID] = mapped_column(
        ForeignKey("providers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    provider: Mapped["Provider"] = relationship("Provider", back_populates="sims")


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    allow_reregistration: Mapped[bool] = mapped_column(Boolean, server_default="TRUE")
    available: Mapped[int] = mapped_column(server_default="0")
    last_active: Mapped[Optional[datetime.datetime]] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now()
    )

    sims: Mapped[List["Sim"]] = relationship(
        "Sim", back_populates="provider", cascade="all, delete", passive_deletes=True
    )

    def is_expired(self, ttl: datetime.timedelta | None) -> bool:
        if ttl is None:
            return False

        return (
            self.last_active is not None
            and datetime.datetime.now(tz=datetime.timezone.utc) - self.last_active > ttl
        )


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
    provider_id: Mapped[UUID]
    probe_id: Mapped[UUID]
    sim_id: Mapped[int]
    sim_iccid: Mapped[Optional[str]]
    sim_imsi: Mapped[Optional[str]]
    command: Mapped[ApduOp]
    payload: Mapped[Optional[bytes]] = mapped_column(LargeBinary)
    sender: Mapped[Sender]
