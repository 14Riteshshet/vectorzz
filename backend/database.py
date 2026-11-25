"""
SookshmaJal – Async database engine and session dependency.
Supports SQLite (dev) and PostgreSQL (prod) via DATABASE_URL.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# ── Engine ─────────────────────────────────────────────────────────────────────
_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=(settings.APP_ENV == "development"),
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


# ── Dependency ─────────────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Init ───────────────────────────────────────────────────────────────────────
async def _seed_demo_plots_if_empty() -> None:
    """Seed 4 sample Tumakuru regional farmer plots if the database is empty."""
    import json
    import uuid
    from sqlalchemy import func, select
    from backend.hydromet import build_timeseries_data
    from backend.models import FarmPlot, TelemetryLog
    from backend.satellite import load_taluk_cache

    async with AsyncSessionLocal() as session:
        count_res = await session.execute(select(func.count(FarmPlot.id)))
        if (count_res.scalar() or 0) > 0:
            return

        samples = [
            {
                "farmer_name": "Ramaiah Gowda",
                "taluk": "Madhugiri",
                "crop_type": "Ragi",
                "area_acres": 2.5,
                "lat": 13.6621,
                "lon": 77.2017,
                "ndvi": 0.09,
                "ndmi": -0.46,
                "ndre": 0.07,
                "drought_stage": "severe_drought",
                "et0": 5.8,
                "precip": 2.4,
                "soil_m": 11.2,
                "v_surv": 234946.0,
                "cache_key": "madhugiri",
            },
            {
                "farmer_name": "Basavaraju",
                "taluk": "Koratagere",
                "crop_type": "Groundnut",
                "area_acres": 2.0,
                "lat": 13.5225,
                "lon": 77.2365,
                "ndvi": 0.18,
                "ndmi": -0.31,
                "ndre": 0.14,
                "drought_stage": "moderate_drought",
                "et0": 5.4,
                "precip": 6.1,
                "soil_m": 16.5,
                "v_surv": 197834.0,
                "cache_key": "koratagere",
            },
            {
                "farmer_name": "Shivanna",
                "taluk": "Chikkanayakanahalli",
                "crop_type": "Ragi",
                "area_acres": 3.0,
                "lat": 13.4318,
                "lon": 76.9336,
                "ndvi": 0.58,
                "ndmi": 0.22,
                "ndre": 0.41,
                "drought_stage": "healthy",
                "et0": 4.2,
                "precip": 28.5,
                "soil_m": 29.4,
                "v_surv": 0.0,
                "cache_key": "cnhalli",
            },
            {
                "farmer_name": "Lakshmi Narayana",
                "taluk": "Tumakuru",
                "crop_type": "Tomato",
                "area_acres": 1.5,
                "lat": 13.3392,
                "lon": 77.1140,
                "ndvi": 0.27,
                "ndmi": -0.16,
                "ndre": 0.21,
                "drought_stage": "early_stress",
                "et0": 5.1,
                "precip": 9.8,
                "soil_m": 19.8,
                "v_surv": 84500.0,
                "cache_key": None,
            },
        ]

        for s in samples:
            h = 0.005
            lat, lon = s["lat"], s["lon"]
            coords = [
                [lon - h, lat - h],
                [lon + h, lat - h],
                [lon + h, lat + h],
                [lon - h, lat + h],
                [lon - h, lat - h],
            ]
            geojson = {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {"farmer": s["farmer_name"], "crop": s["crop_type"]},
            }
            plot_id = str(uuid.uuid4())
            session.add(
                FarmPlot(
                    id=plot_id,
                    farmer_name=s["farmer_name"],
                    taluk=s["taluk"],
                    crop_type=s["crop_type"],
                    area_acres=s["area_acres"],
                    polygon_geojson=json.dumps(geojson),
                    centroid_lat=lat,
                    centroid_lon=lon,
                    ndvi=s["ndvi"],
                    ndmi=s["ndmi"],
                    ndre=s["ndre"],
                    drought_stage=s["drought_stage"],
                )
            )
            cached_ts = None
            if s["cache_key"]:
                cache = load_taluk_cache(
                    settings.FALLBACK_CACHE_DIR, s["cache_key"], coords
                )
                cached_ts = cache.get("time_series") if cache else None
            ts_raw = build_timeseries_data(
                ndvi=s["ndvi"],
                ndmi=s["ndmi"],
                ndre=s["ndre"],
                et0_mm_day=s["et0"],
                soil_moisture_pct=s["soil_m"],
                drought_stage=s["drought_stage"],
                scene_date="2026-10-30",
                cached_timeseries=cached_ts,
                data_source="fallback_cache" if cached_ts else "demo_seed",
            )
            session.add(
                TelemetryLog(
                    plot_id=plot_id,
                    et0_mm_day=s["et0"],
                    precipitation_mm=s["precip"],
                    soil_moisture_pct=s["soil_m"],
                    survival_liters=s["v_surv"],
                    ndvi=s["ndvi"],
                    ndmi=s["ndmi"],
                    ndre=s["ndre"],
                    scene_date="2026-10-30",
                    cloud_cover_pct=4.5,
                    data_source="fallback_cache" if cached_ts else "demo_seed",
                    extra_meta={"time_series": ts_raw},
                )
            )

        await session.commit()
        logger.info("Seeded %d regional demo plots.", len(samples))


async def init_db() -> None:
    """Create all tables (idempotent) and seed demo plots if empty."""
    # Import models so metadata is populated
    from backend import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_demo_plots_if_empty()
    logger.info("Database initialised at %s", settings.DATABASE_URL)
