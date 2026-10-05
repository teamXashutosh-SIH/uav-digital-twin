from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EngineTelemetryModel(Base):
    __tablename__ = "engine_telemetry"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    schema_version: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    vehicle_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    engine_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    mission_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    sequence: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    rpm: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    cht_c: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    egt_c: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    oil_pressure_kpa: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    oil_temperature_c: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    fuel_flow_gph: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    vibration_g: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    battery_voltage_v: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    alternator_current_a: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    injection_timing_deg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    altitude_m: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    ambient_temperature_c: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    throttle_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    quality_flags: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
    )


class EngineFaultEventModel(Base):
    __tablename__ = "engine_fault_events"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    engine_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    vehicle_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    mission_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    fault: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    severity: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    cleared_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    event_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )


class EngineMissionModel(Base):
    __tablename__ = "engine_missions"
    __table_args__ = (
        UniqueConstraint(
            "mission_id",
            name="uq_engine_missions_mission_id",
        ),
        Index(
            "uq_engine_missions_active_engine",
            "engine_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    mission_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    engine_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    vehicle_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    mission_metadata: Mapped[dict | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )