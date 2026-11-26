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
    """Seed multi-district Karnataka reference plots without altering existing records."""
    import json
    import uuid
    from sqlalchemy import select
    from backend.hydromet import build_timeseries_data
    from backend.models import FarmPlot, TelemetryLog
    from backend.satellite import load_taluk_cache

    async with AsyncSessionLocal() as session:
        existing_res = await session.execute(
            select(FarmPlot)
        )
        existing_rows = existing_res.scalars().all()
        existing_keys = {(r.farmer_name, r.taluk): r for r in existing_rows}

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
                "photo_lat": 13.6618,
                "photo_lon": 77.1958,
                "geolock_status": "VERIFIED_IN_REGION",
                "region_match": True,
                "distance_km": 0.03,
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
                "photo_lat": 13.5210,
                "photo_lon": 77.2330,
                "geolock_status": "VERIFIED_IN_REGION",
                "region_match": True,
                "distance_km": 0.08,
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
                "photo_lat": 12.9716,
                "photo_lon": 77.5946,
                "geolock_status": "OUTSIDE_REGION_WARNING",
                "region_match": False,
                "distance_km": 130.14,
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
                "photo_lat": 14.4100,
                "photo_lon": 76.7200,
                "geolock_status": "DISTRICT_MATCH_NEARBY",
                "region_match": True,
                "distance_km": 12.98,
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
            {
                "farmer_name": "Muniyappa",
                "phone_number": "+91 98455 11209",
                "district": "Kolar",
                "taluk": "Mulbagal",
                "hobli": "Kasaba",
                "village": "Byrakur",
                "survey_no": "19/3",
                "crop_type": "Ragi",
                "area_acres": 2.2,
                "irrigation_source": "Borewell",
                "observed_symptoms": ["Leaf Wilting"],
                "pmfby_eligible": "ELIGIBLE — Severe Moisture Deficit",
                "lat": 13.1636,
                "lon": 78.3944,
                "photo_lat": 13.1640,
                "photo_lon": 78.3948,
                "geolock_status": "VERIFIED_IN_REGION",
                "region_match": True,
                "distance_km": 0.06,
                "ndvi": 0.11,
                "ndmi": -0.42,
                "ndre": 0.09,
                "drought_stage": "severe_drought",
                "et0": 5.7,
                "precip": 2.8,
                "soil_m": 11.9,
                "v_surv": 218400.0,
                "cache_key": "madhugiri",
            },
            {
                "farmer_name": "Basanagouda Biradar",
                "phone_number": "+91 94480 65211",
                "district": "Vijayapura",
                "taluk": "Indi",
                "hobli": "Indi",
                "village": "Horti",
                "survey_no": "77/2",
                "crop_type": "Pigeon Pea",
                "area_acres": 4.0,
                "irrigation_source": "Purely Rain-Fed",
                "observed_symptoms": ["Soil Cracking", "Stunted Growth"],
                "pmfby_eligible": "ELIGIBLE — Severe Moisture Deficit",
                "lat": 17.1755,
                "lon": 75.9593,
                "ndvi": 0.10,
                "ndmi": -0.44,
                "ndre": 0.08,
                "drought_stage": "severe_drought",
                "et0": 6.2,
                "precip": 1.5,
                "soil_m": 10.1,
                "v_surv": 295000.0,
                "cache_key": "madhugiri",
            },
            {
                "farmer_name": "Eranna",
                "phone_number": "+91 99804 71230",
                "district": "Ballari",
                "taluk": "Siruguppa",
                "hobli": "Tekkalakote",
                "village": "Raravi",
                "survey_no": "25/4",
                "crop_type": "Cotton",
                "area_acres": 3.5,
                "irrigation_source": "Borewell",
                "observed_symptoms": ["Leaf Wilting"],
                "pmfby_eligible": "WATCHLIST — Moderate Stress",
                "lat": 15.6326,
                "lon": 76.8981,
                "ndvi": 0.21,
                "ndmi": -0.26,
                "ndre": 0.17,
                "drought_stage": "moderate_drought",
                "et0": 5.6,
                "precip": 6.0,
                "soil_m": 15.2,
                "v_surv": 182000.0,
                "cache_key": "koratagere",
            },
            {
                "farmer_name": "Sharanappa",
                "phone_number": "+91 97411 30492",
                "district": "Koppal",
                "taluk": "Yelburga",
                "hobli": "Kuknur",
                "village": "Bhanapur",
                "survey_no": "48/1",
                "crop_type": "Maize",
                "area_acres": 3.2,
                "irrigation_source": "Purely Rain-Fed",
                "observed_symptoms": ["Soil Cracking"],
                "pmfby_eligible": "ELIGIBLE — Severe Moisture Deficit",
                "lat": 15.6229,
                "lon": 76.0170,
                "ndvi": 0.12,
                "ndmi": -0.40,
                "ndre": 0.10,
                "drought_stage": "severe_drought",
                "et0": 5.9,
                "precip": 2.2,
                "soil_m": 11.4,
                "v_surv": 248000.0,
                "cache_key": "madhugiri",
            },
            {
                "farmer_name": "Hanumantharayappa",
                "phone_number": "+91 96633 82104",
                "district": "Raichur",
                "taluk": "Lingsugur",
                "hobli": "Mudgal",
                "village": "Maski",
                "survey_no": "102/2",
                "crop_type": "Sorghum",
                "area_acres": 5.0,
                "irrigation_source": "Purely Rain-Fed",
                "observed_symptoms": ["Leaf Wilting"],
                "pmfby_eligible": "WATCHLIST — Moderate Stress",
                "lat": 16.1558,
                "lon": 76.5210,
                "ndvi": 0.22,
                "ndmi": -0.24,
                "ndre": 0.18,
                "drought_stage": "moderate_drought",
                "et0": 5.5,
                "precip": 6.8,
                "soil_m": 16.0,
                "v_surv": 205000.0,
                "cache_key": "koratagere",
            },
            {
                "farmer_name": "Malleshappa",
                "phone_number": "+91 94812 51908",
                "district": "Haveri",
                "taluk": "Ranebennur",
                "hobli": "Kuppelur",
                "village": "Halageri",
                "survey_no": "14/3",
                "crop_type": "Maize",
                "area_acres": 2.8,
                "irrigation_source": "Canal/Tank",
                "observed_symptoms": [],
                "pmfby_eligible": "NOT ELIGIBLE — Normal Moisture",
                "lat": 14.6202,
                "lon": 75.6295,
                "ndvi": 0.56,
                "ndmi": 0.21,
                "ndre": 0.40,
                "drought_stage": "healthy",
                "et0": 4.3,
                "precip": 25.4,
                "soil_m": 28.0,
                "v_surv": 0.0,
                "cache_key": "cnhalli",
            },
        ]

        inserted = 0
        updated = 0
        for s in samples:
            key = (s["farmer_name"], s["taluk"])
            if key in existing_keys:
                row = existing_keys[key]
                if (
                    row.phone_number == s["phone_number"]
                    and row.entry_source != "Seeded Sample"
                ):
                    row.entry_source = "Seeded Sample"
                    updated += 1
                continue
            inserted += 1
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
                    photo_lat=s.get("photo_lat"),
                    photo_lon=s.get("photo_lon"),
                    photo_timestamp="2026-10-30T10:15:00Z" if s.get("photo_lat") else None,
                    geolock_status=s.get("geolock_status", "MISSING_GPS"),
                    region_match=s.get("region_match", False),
                    distance_km=s.get("distance_km"),
                    pmfby_eligible=s["pmfby_eligible"],
                    polygon_geojson=json.dumps(geojson),
                    centroid_lat=lat,
                    centroid_lon=lon,
                    ndvi=s["ndvi"],
                    ndmi=s["ndmi"],
                    ndre=s["ndre"],
                    drought_stage=s["drought_stage"],
                    entry_source="Seeded Sample",
                    audit_status="PENDING",
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

        if inserted or updated:
            await session.commit()
            logger.info("Seeded %d regional demo plots (tagged %d).", inserted, updated)


async def _ensure_sqlite_columns(conn) -> None:
    """Idempotently add Phase 3 audit/source columns to existing SQLite databases."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        return
    from sqlalchemy import text

    res = await conn.execute(text("PRAGMA table_info(farm_plots)"))
    existing = {row[1] for row in res.fetchall()}
    migrations = [
        ("entry_source", "VARCHAR(32) DEFAULT 'Live Farmer Entry'"),
        ("audit_status", "VARCHAR(24) DEFAULT 'PENDING'"),
        ("officer_remark", "VARCHAR(300)"),
        ("reviewed_at", "DATETIME"),
    ]
    for col, ddl in migrations:
        if col not in existing:
            await conn.execute(text(f"ALTER TABLE farm_plots ADD COLUMN {col} {ddl}"))


async def init_db() -> None:
    """Create all tables (idempotent) and seed demo plots if empty."""
    # Import models so metadata is populated
    from backend import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_sqlite_columns(conn)
    await _seed_demo_plots_if_empty()
    logger.info("Database initialised at %s", settings.DATABASE_URL)
