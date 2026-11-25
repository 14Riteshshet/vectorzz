"""
SookshmaJal – SQLAlchemy ORM models.
FarmPlot  – stores plot metadata and computed indices.
TelemetryLog – time-series hydro-met readings per plot.
ClaimDossier – PMFBY PDF claim records with SHA-256 anchoring.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _now() -> datetime:
    return datetime.utcnow()


def _uuid() -> str:
    return str(uuid.uuid4())


class FarmPlot(Base):
    __tablename__ = "farm_plots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    farmer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    taluk: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), default="Tumakuru")
    crop_type: Mapped[str] = mapped_column(String(100), nullable=False)
    area_acres: Mapped[float] = mapped_column(Float, nullable=False)
    polygon_geojson: Mapped[str] = mapped_column(Text, nullable=False)  # GeoJSON string
    centroid_lat: Mapped[float] = mapped_column(Float, nullable=False)
    centroid_lon: Mapped[float] = mapped_column(Float, nullable=False)

    # Latest satellite analysis
    ndvi: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndre: Mapped[float | None] = mapped_column(Float, nullable=True)
    drought_stage: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    # Relationships
    telemetry_logs: Mapped[list[TelemetryLog]] = relationship(
        "TelemetryLog", back_populates="plot", cascade="all, delete-orphan"
    )
    claim_dossiers: Mapped[list[ClaimDossier]] = relationship(
        "ClaimDossier", back_populates="plot", cascade="all, delete-orphan"
    )


class TelemetryLog(Base):
    __tablename__ = "telemetry_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("farm_plots.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)

    # Hydro-met data
    et0_mm_day: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    soil_moisture_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    survival_liters: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Satellite indices
    ndvi: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    ndre: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Sentinel-2 scene metadata
    scene_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    data_source: Mapped[str] = mapped_column(String(50), default="planetary_computer")

    extra_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    plot: Mapped[FarmPlot] = relationship("FarmPlot", back_populates="telemetry_logs")


class ClaimDossier(Base):
    __tablename__ = "claim_dossiers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("farm_plots.id", ondelete="CASCADE"), nullable=False
    )
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # PDF tracking
    pdf_path: Mapped[str] = mapped_column(String(512), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    pdf_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Claim payload (JSON snapshot of analysis at claim time)
    claim_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Status
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    plot: Mapped[FarmPlot] = relationship("FarmPlot", back_populates="claim_dossiers")
