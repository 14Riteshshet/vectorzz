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
    """Seed 8 sample multi-district Karnataka farmer plots if the database is empty."""
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
                "phone_number": "+91 98451 22101",
                "district": "Tumakuru",
                "taluk": "Madhugiri",
                "hobli": "Kasaba",
                "village": "Kodigenahalli",
                "survey_no": "42/1",
                "crop_type": "Ragi",
                "area_acres": 2.4,
                "irrigation_source": "Purely Rain-Fed",
                "observed_symptoms": ["Soil Cracking", "Leaf Wilting"],
                "pmfby_eligible": "ELIGIBLE — Severe Moisture Deficit",
                "lat": 13.6616,
                "lon": 77.1956,
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
                "phone_number": "+91 98451 33412",
                "district": "Tumakuru",
                "taluk": "Koratagere",
                "hobli": "Kasaba",
                "village": "Kolala",
                "survey_no": "31/1",
                "crop_type": "Groundnut",
                "area_acres": 2.0,
                "irrigation_source": "Borewell",
                "observed_symptoms": ["Leaf Wilting"],
                "pmfby_eligible": "WATCHLIST — Moderate Stress",
                "lat": 13.5205,
                "lon": 77.2325,
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
                "phone_number": "+91 97400 18923",
                "district": "Tumakuru",
                "taluk": "Chikkanayakanahalli",
                "hobli": "Kasaba",
                "village": "Huliyar",
                "survey_no": "11/2",
                "crop_type": "Ragi",
                "area_acres": 3.0,
                "irrigation_source": "Canal/Tank",
                "observed_symptoms": [],
                "pmfby_eligible": "NOT ELIGIBLE — Normal Moisture",
                "lat": 13.4297,
                "lon": 76.9298,
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
                "phone_number": "+91 99002 44810",
                "district": "Tumakuru",
                "taluk": "Tumakuru",
                "hobli": "Kasaba",
                "village": "Kyathsandra",
                "survey_no": "61/1",
                "crop_type": "Tomato",
                "area_acres": 1.6,
                "irrigation_source": "Borewell",
                "observed_symptoms": ["Flower Drop"],
                "pmfby_eligible": "WATCHLIST — Moderate Stress",
                "lat": 13.3383,
                "lon": 77.1114,
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
            {
                "farmer_name": "Narasimhaiah",
                "phone_number": "+91 94481 77621",
                "district": "Tumakuru",
                "taluk": "Pavagada",
                "hobli": "Kasaba",
                "village": "Y.N. Hosakote",
                "survey_no": "54/1",
                "crop_type": "Groundnut",
                "area_acres": 4.2,
                "irrigation_source": "Purely Rain-Fed",
                "observed_symptoms": ["Soil Cracking", "Borewell Dried"],
                "pmfby_eligible": "ELIGIBLE — Severe Moisture Deficit",
                "lat": 14.0999,
                "lon": 77.2760,
                "ndvi": 0.08,
                "ndmi": -0.49,
                "ndre": 0.06,
                "drought_stage": "severe_drought",
                "et0": 6.1,
                "precip": 1.2,
                "soil_m": 9.8,
                "v_surv": 312400.0,
                "cache_key": "madhugiri",
            },
            {
                "farmer_name": "Thippeswamy",
                "phone_number": "+91 96112 55091",
                "district": "Chitradurga",
                "taluk": "Challakere",
                "hobli": "Kasaba",
                "village": "Nayakanahatti",
                "survey_no": "88/1",
                "crop_type": "Groundnut",
                "area_acres": 3.8,
                "irrigation_source": "Purely Rain-Fed",
                "observed_symptoms": ["Soil Cracking", "Leaf Wilting"],
                "pmfby_eligible": "ELIGIBLE — Severe Moisture Deficit",
                "lat": 14.3129,
                "lon": 76.6529,
                "ndvi": 0.09,
                "ndmi": -0.45,
                "ndre": 0.08,
                "drought_stage": "severe_drought",
                "et0": 6.0,
                "precip": 2.0,
                "soil_m": 10.6,
                "v_surv": 288900.0,
                "cache_key": "madhugiri",
            },
            {
                "farmer_name": "Venkateshappa",
                "phone_number": "+91 98801 66712",
                "district": "Chikkaballapur",
                "taluk": "Bagepalli",
                "hobli": "Kasaba",
                "village": "Chelur",
                "survey_no": "34/1",
                "crop_type": "Groundnut",
                "area_acres": 2.6,
                "irrigation_source": "Borewell",
                "observed_symptoms": ["Borewell Dried", "Leaf Wilting"],
                "pmfby_eligible": "WATCHLIST — Moderate Stress",
                "lat": 13.7826,
                "lon": 77.7926,
                "ndvi": 0.19,
                "ndmi": -0.29,
                "ndre": 0.15,
                "drought_stage": "moderate_drought",
                "et0": 5.5,
                "precip": 5.4,
                "soil_m": 15.8,
                "v_surv": 215400.0,
                "cache_key": "koratagere",
            },
            {
                "farmer_name": "Mallikarjun Patil",
                "phone_number": "+91 94490 88234",
                "district": "Kalaburagi",
                "taluk": "Kalaburagi",
                "hobli": "Kamalapur",
                "village": "Kamalapur",
                "survey_no": "114/1",
                "crop_type": "Sorghum",
                "area_acres": 4.5,
                "irrigation_source": "Canal/Tank",
                "observed_symptoms": [],
                "pmfby_eligible": "NOT ELIGIBLE — Normal Moisture",
                "lat": 17.3300,
                "lon": 76.8341,
                "ndvi": 0.54,
                "ndmi": 0.19,
                "ndre": 0.39,
                "drought_stage": "healthy",
                "et0": 4.5,
                "precip": 24.0,
                "soil_m": 27.2,
                "v_surv": 0.0,
                "cache_key": "cnhalli",
            },
        ]

        for s in samples:
            h = 0.004
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
                "properties": {
                    "farmer": s["farmer_name"],
                    "crop": s["crop_type"],
                    "survey_no": s["survey_no"],
                },
            }
            plot_id = str(uuid.uuid4())
            session.add(
                FarmPlot(
                    id=plot_id,
                    farmer_name=s["farmer_name"],
                    phone_number=s["phone_number"],
                    district=s["district"],
                    taluk=s["taluk"],
                    hobli=s["hobli"],
                    village=s["village"],
                    survey_no=s["survey_no"],
                    crop_type=s["crop_type"],
                    area_acres=s["area_acres"],
                    irrigation_source=s["irrigation_source"],
                    observed_symptoms=s["observed_symptoms"],
                    pmfby_eligible=s["pmfby_eligible"],
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
