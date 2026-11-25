"""
SookshmaJal – FastAPI application entry point.
Routes:
  GET  /health                        – liveness probe
  POST /api/analyze-plot              – full satellite + hydromet analysis
  GET  /api/verify/{sha256_hash}      – PMFBY dossier hash verification
  GET  /api/plots                     – list all saved plots
  Static mount at /                   – serves frontend/
"""

import json
import logging
import uuid as _uuid_mod
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.database import get_db, init_db
from backend.hydromet import (
    build_crop_irrigation_guidance,
    build_timeseries_data,
    get_hydromet_data,
)
from backend.models import ClaimDossier, FarmPlot, TelemetryLog
from backend.pdf_gen import generate_pmfby_pdf
from backend.satellite import fetch_sentinel2_indices, load_taluk_cache
from backend.schemas import (
    AnalyzePlotRequest,
    AnalyzePlotResponse,
    CropIrrigationGuidance,
    DroughtAssessment,
    GenerateDossierResponse,
    HealthResponse,
    HydrometData,
    PlotsListResponse,
    PlotSummary,
    SatelliteIndices,
    TimeSeriesData,
    VerifyDossierResponse,
)
from backend.voice import build_kannada_advisory_text, generate_voice_advisory

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address

    _SLOWAPI = True
except ImportError:
    _SLOWAPI = False

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s – %(message)s"
)

settings = get_settings()

# ── Rate limiter ───────────────────────────────────────────────────────────────
if _SLOWAPI:
    limiter = Limiter(key_func=get_remote_address)
    _rate_limit = limiter.limit
else:

    def _rate_limit(_limit_value: str):
        def _decorator(func):
            return func

        return _decorator


# ── Lifespan ───────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("SookshmaJal starting up – initialising database …")
    await init_db()
    Path(settings.PDF_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("Ready. Team VECTORZZ · Hackwarts 2026 🌱")
    yield
    logger.info("SookshmaJal shutting down.")


DbSession = Annotated[AsyncSession, Depends(get_db)]


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SookshmaJal",
    description=(
        "Zero-hardware plot-level Sentinel-2 moisture & FAO-56 ET₀ decision engine "
        "for drought survival and PMFBY crop-loss ground-truthing in Tumakuru, Karnataka. "
        "Team VECTORZZ · Hackwarts 2026 AgriTech Track."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

if _SLOWAPI:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Drought classification ─────────────────────────────────────────────────────
def _classify_drought(ndvi: float, ndmi: float) -> DroughtAssessment:
    """
    Classify drought stage based on NDVI and NDMI thresholds.
    Thresholds calibrated for Tumakuru dryland crops.
    """
    if ndmi >= 0.0 and ndvi >= 0.35:
        stage = "healthy"
        label = "Healthy — No Water Stress"
        color = "color-2"  # #0066CC
        rec_en = (
            "Your crop shows no signs of water stress. Continue regular irrigation schedule. "
            "Monitor weekly via SookshmaJal."
        )
        rec_kn = build_kannada_advisory_text(stage, 0.0, 0.0, ndmi)
    elif ndmi >= -0.2 or ndvi >= 0.2:
        stage = "early_stress"
        label = "Early Stress — Increase Irrigation"
        color = "color-5"  # #FF791B
        rec_en = (
            "Early moisture stress detected. Increase irrigation frequency. "
            "Apply mulch to reduce soil evaporation. Monitor soil moisture daily."
        )
        rec_kn = build_kannada_advisory_text(stage, 0.0, 0.0, ndmi)
    elif ndmi >= -0.4 or ndvi >= 0.1:
        stage = "moderate_drought"
        label = "Moderate Drought — Urgent Action Required"
        color = "color-5"  # #FF791B warning orange (not red-critical yet)
        rec_en = (
            "Moderate drought stress. Apply deficit irrigation immediately. "
            "Contact taluk agricultural officer. Begin PMFBY documentation."
        )
        rec_kn = build_kannada_advisory_text(stage, 0.0, 0.0, ndmi)
    else:
        stage = "severe_drought"
        label = "Severe Drought — File PMFBY Claim Now"
        color = "color-3"  # #B64400
        rec_en = (
            "ALERT: Severe drought. Immediate emergency irrigation required. "
            "File PMFBY crop loss claim now. Photograph field conditions as evidence."
        )
        rec_kn = build_kannada_advisory_text(stage, 0.0, 0.0, ndmi)

    return DroughtAssessment(
        stage=stage,
        stage_label=label,
        color_token=color,
        ndmi_threshold=ndmi,
        ndvi_threshold=ndvi,
        recommendation_en=rec_en,
        recommendation_kn=rec_kn,
    )


# ── Centroid helper ────────────────────────────────────────────────────────────
def _compute_centroid(coords: list[list[float]]) -> tuple[float, float]:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lons) / len(lons), sum(lats) / len(lats)


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Liveness probe – returns service status and team metadata."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        team="VECTORZZ",
        hackathon="Hackwarts 2026",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.post("/api/analyze-plot", response_model=AnalyzePlotResponse, tags=["Analysis"])
@_rate_limit(settings.RATE_LIMIT_ANALYZE)
async def analyze_plot(
    body: AnalyzePlotRequest,
    request: Request,
    db: DbSession,
):
    """
    Full satellite + hydromet analysis pipeline for a farm plot.
    - Fetches Sentinel-2 indices via Planetary Computer (or fallback cache)
    - Computes FAO-56 ET₀, precipitation, soil moisture, survival litres
    - Classifies drought stage
    - Generates Kannada voice advisory (Sarvam AI or fallback text)
    - Generates PMFBY PDF dossier with SHA-256 hash + QR code
    - Persists FarmPlot, TelemetryLog, ClaimDossier records
    """
    lon_c, lat_c = _compute_centroid(body.polygon_coordinates)
    taluk_key = body.taluk.lower().replace(" ", "")
    taluk_cache = load_taluk_cache(
        settings.FALLBACK_CACHE_DIR,
        taluk_key,
        body.polygon_coordinates,
    )

    # ── 1. Satellite indices ─────────────────────────────────────────────────
    try:
        sat_raw = fetch_sentinel2_indices(
            body.polygon_coordinates,
            fallback_cache_dir=settings.FALLBACK_CACHE_DIR,
            taluk_key=taluk_key,
            use_fallback=body.use_fallback,
        )
    except Exception as exc:
        logger.error("Satellite fetch error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Satellite data unavailable: {exc}",
        ) from exc

    sat_indices = SatelliteIndices(**sat_raw)

    # ── 2. Drought classification ────────────────────────────────────────────
    drought = _classify_drought(sat_indices.ndvi, sat_indices.ndmi)

    # ── 3. Hydro-met ─────────────────────────────────────────────────────────
    fallback_hm = taluk_cache.get("hydromet") if taluk_cache else None
    try:
        hm_raw = get_hydromet_data(
            lat_c,
            lon_c,
            body.area_acres,
            body.crop_type,
            use_fallback=body.use_fallback,
            fallback_hydromet=fallback_hm,
        )
    except Exception as exc:
        logger.error("Hydromet error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Hydromet data unavailable: {exc}",
        ) from exc

    # Update drought recommendations with actual ET₀ / survival litres
    drought.recommendation_kn = build_kannada_advisory_text(
        drought.stage,
        hm_raw["et0_mm_day"],
        hm_raw["survival_liters"],
        sat_indices.ndmi,
        crop_type=body.crop_type,
    )

    hydromet_data = HydrometData(
        et0_mm_day=hm_raw["et0_mm_day"],
        precipitation_mm=hm_raw["precipitation_mm"],
        soil_moisture_0_7cm_pct=hm_raw["soil_moisture_0_7cm_pct"],
        survival_liters=hm_raw["survival_liters"],
        deficit_mm=hm_raw["deficit_mm"],
        open_meteo_timestamp=hm_raw["open_meteo_timestamp"],
    )

    # ── 3b. Multi-point Kharif time-series & Farmer irrigation guidance ──────
    cached_ts = sat_raw.get("time_series") or (
        taluk_cache.get("time_series") if taluk_cache else None
    )
    ts_raw = build_timeseries_data(
        ndvi=sat_indices.ndvi,
        ndmi=sat_indices.ndmi,
        ndre=sat_indices.ndre,
        et0_mm_day=hydromet_data.et0_mm_day,
        soil_moisture_pct=hydromet_data.soil_moisture_0_7cm_pct,
        drought_stage=drought.stage,
        scene_date=sat_indices.scene_date,
        cached_timeseries=cached_ts
        if sat_indices.data_source != "planetary_computer"
        else None,
        data_source=sat_indices.data_source,
    )
    time_series = TimeSeriesData(**ts_raw)

    guidance_raw = build_crop_irrigation_guidance(
        crop_type=body.crop_type,
        drought_stage=drought.stage,
        et0_mm_day=hydromet_data.et0_mm_day,
        soil_moisture_pct=hydromet_data.soil_moisture_0_7cm_pct,
        survival_liters=hydromet_data.survival_liters,
        area_acres=body.area_acres,
    )
    irrigation_guidance = CropIrrigationGuidance(**guidance_raw)

    # ── 4. Persist FarmPlot ──────────────────────────────────────────────────
    plot_id = str(_uuid_mod.uuid4())
    geojson_str = json.dumps(body.to_geojson_polygon())

    db_plot = FarmPlot(
        id=plot_id,
        farmer_name=body.farmer_name,
        taluk=body.taluk,
        crop_type=body.crop_type,
        area_acres=body.area_acres,
        polygon_geojson=geojson_str,
        centroid_lat=lat_c,
        centroid_lon=lon_c,
        ndvi=sat_indices.ndvi,
        ndmi=sat_indices.ndmi,
        ndre=sat_indices.ndre,
        drought_stage=drought.stage,
    )
    db.add(db_plot)

    # TelemetryLog
    db_telem = TelemetryLog(
        plot_id=plot_id,
        et0_mm_day=hydromet_data.et0_mm_day,
        precipitation_mm=hydromet_data.precipitation_mm,
        soil_moisture_pct=hydromet_data.soil_moisture_0_7cm_pct,
        survival_liters=hydromet_data.survival_liters,
        ndvi=sat_indices.ndvi,
        ndmi=sat_indices.ndmi,
        ndre=sat_indices.ndre,
        scene_date=sat_indices.scene_date,
        cloud_cover_pct=sat_indices.cloud_cover_pct,
        data_source=sat_indices.data_source,
        extra_meta={"time_series": ts_raw},
    )
    db.add(db_telem)
    await db.flush()

    # ── 5. Voice advisory ────────────────────────────────────────────────────
    audio_b64, advisory_kn = generate_voice_advisory(
        farmer_name=body.farmer_name,
        crop_type=body.crop_type,
        drought_stage=drought.stage,
        et0=hydromet_data.et0_mm_day,
        survival_liters=hydromet_data.survival_liters,
        ndvi=sat_indices.ndvi,
        ndmi=sat_indices.ndmi,
    )
    if advisory_kn:
        drought.recommendation_kn = advisory_kn

    audio_source = (
        "sarvam_bulbul_v1"
        if (audio_b64 and settings.SARVAM_API_KEY)
        else ("offline_wav_fallback" if audio_b64 else "text_only")
    )

    # ── 6. PMFBY PDF ─────────────────────────────────────────────────────────
    pdf_sha256: Optional[str] = None
    pdf_download_url: Optional[str] = None

    sat_payload = {k: v for k, v in sat_raw.items() if k != "time_series"}
    claim_payload = {
        "plot_id": plot_id,
        "farmer_name": body.farmer_name,
        "crop_type": body.crop_type,
        "taluk": body.taluk,
        "area_acres": body.area_acres,
        "centroid_lat": lat_c,
        "centroid_lon": lon_c,
        "satellite": sat_payload,
        "drought": drought.model_dump(),
        "hydromet": hm_raw,
        "time_series": ts_raw,
    }

    try:
        base_url = str(request.base_url).rstrip("/")
        pdf_path, pdf_sha256 = generate_pmfby_pdf(
            payload=claim_payload,
            output_dir=settings.PDF_OUTPUT_DIR,
            verify_base_url=base_url,
        )
        pdf_download_url = f"{base_url}/api/pdf/{Path(pdf_path).name}"

        # ClaimDossier record
        pdf_size = Path(pdf_path).stat().st_size if Path(pdf_path).exists() else 0
        db_claim = ClaimDossier(
            plot_id=plot_id,
            pdf_path=pdf_path,
            sha256_hash=pdf_sha256,
            pdf_size_bytes=pdf_size,
            claim_payload=claim_payload,
            is_verified=True,
            verified_at=datetime.utcnow(),
        )
        db.add(db_claim)
        await db.flush()

    except Exception as exc:
        logger.warning("PDF generation failed (non-fatal): %s", exc)

    analysed_at = datetime.now(timezone.utc).isoformat()

    return AnalyzePlotResponse(
        plot_id=plot_id,
        farmer_name=body.farmer_name,
        taluk=body.taluk,
        crop_type=body.crop_type,
        area_acres=body.area_acres,
        centroid_lat=lat_c,
        centroid_lon=lon_c,
        satellite=sat_indices,
        drought=drought,
        hydromet=hydromet_data,
        time_series=time_series,
        irrigation_guidance=irrigation_guidance,
        audio_base64=audio_b64,
        audio_source=audio_source,
        pdf_sha256=pdf_sha256,
        pdf_download_url=pdf_download_url,
        analysed_at=analysed_at,
    )


@app.get(
    "/api/verify/{sha256_hash}",
    response_model=VerifyDossierResponse,
    tags=["Verification"],
)
async def verify_dossier(sha256_hash: str, db: DbSession):
    """
    Verify a PMFBY dossier by its SHA-256 hash.
    Returns the claim metadata if found, confirming tamper-evident anchoring.
    """
    # Validate hash format
    if len(sha256_hash) != 64 or not all(
        c in "0123456789abcdef" for c in sha256_hash.lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid SHA-256 hash format. Must be 64 hex characters.",
        )

    stmt = select(ClaimDossier).where(ClaimDossier.sha256_hash == sha256_hash.lower())
    result = await db.execute(stmt)
    dossier = result.scalar_one_or_none()

    if dossier is None:
        return VerifyDossierResponse(
            sha256_hash=sha256_hash,
            is_valid=False,
            plot_id=None,
            farmer_name=None,
            generated_at=None,
            message="Dossier not found. Hash may be invalid or document may have been tampered with.",
        )

    # Load associated plot
    stmt2 = select(FarmPlot).where(FarmPlot.id == dossier.plot_id)
    res2 = await db.execute(stmt2)
    plot = res2.scalar_one_or_none()

    return VerifyDossierResponse(
        sha256_hash=sha256_hash,
        is_valid=True,
        plot_id=dossier.plot_id,
        farmer_name=plot.farmer_name if plot else None,
        generated_at=dossier.generated_at.isoformat() if dossier.generated_at else None,
        claim_payload=dossier.claim_payload,
        message="✅ Dossier verified. SHA-256 hash matches registered PMFBY claim.",
    )


@app.get("/api/plots", response_model=PlotsListResponse, tags=["Plots"])
async def list_plots(db: DbSession):
    """Return a summary list of all analysed farm plots."""
    stmt = select(FarmPlot).order_by(FarmPlot.created_at.desc()).limit(100)
    result = await db.execute(stmt)
    plots = result.scalars().all()

    summaries = [
        PlotSummary(
            plot_id=p.id,
            farmer_name=p.farmer_name,
            taluk=p.taluk,
            crop_type=p.crop_type,
            area_acres=p.area_acres,
            drought_stage=p.drought_stage,
            ndvi=p.ndvi,
            ndmi=p.ndmi,
            created_at=p.created_at.isoformat(),
        )
        for p in plots
    ]
    return PlotsListResponse(total=len(summaries), plots=summaries)


@app.post(
    "/api/plots/{plot_id}/dossier",
    response_model=GenerateDossierResponse,
    tags=["Verification"],
)
async def generate_plot_dossier(
    plot_id: str,
    request: Request,
    db: DbSession,
):
    """
    Generate (or confirm) a tamper-evident PMFBY Audit Dossier PDF for a plot
    and return its ClaimDossier SHA-256 hash and verification status.
    """
    plot_res = await db.execute(select(FarmPlot).where(FarmPlot.id == plot_id))
    plot = plot_res.scalar_one_or_none()
    if plot is None:
        raise HTTPException(status_code=404, detail="Plot not found.")

    base_url = str(request.base_url).rstrip("/")

    claim_res = await db.execute(
        select(ClaimDossier)
        .where(ClaimDossier.plot_id == plot_id)
        .order_by(ClaimDossier.generated_at.desc())
    )
    existing_claim = claim_res.scalars().first()

    if existing_claim and Path(existing_claim.pdf_path).exists():
        if not existing_claim.is_verified:
            existing_claim.is_verified = True
            existing_claim.verified_at = datetime.utcnow()
            await db.flush()
        return GenerateDossierResponse(
            plot_id=plot_id,
            farmer_name=plot.farmer_name,
            sha256_hash=existing_claim.sha256_hash,
            pdf_download_url=f"{base_url}/api/pdf/{Path(existing_claim.pdf_path).name}",
            pdf_size_bytes=existing_claim.pdf_size_bytes
            or Path(existing_claim.pdf_path).stat().st_size,
            is_verified=True,
            generated_at=existing_claim.generated_at.isoformat(),
            verified_at=existing_claim.verified_at.isoformat()
            if existing_claim.verified_at
            else None,
            message="PMFBY Audit Dossier verified and ready for download.",
        )

    telem_res = await db.execute(
        select(TelemetryLog)
        .where(TelemetryLog.plot_id == plot_id)
        .order_by(TelemetryLog.recorded_at.desc())
    )
    telem = telem_res.scalars().first()

    drought = _classify_drought(plot.ndvi or 0.0, plot.ndmi or 0.0)
    et0 = telem.et0_mm_day if telem and telem.et0_mm_day is not None else 4.8
    precip = (
        telem.precipitation_mm if telem and telem.precipitation_mm is not None else 10.0
    )
    soil_m = (
        telem.soil_moisture_pct
        if telem and telem.soil_moisture_pct is not None
        else 18.0
    )
    v_surv = (
        telem.survival_liters if telem and telem.survival_liters is not None else 0.0
    )
    ts_meta = (telem.extra_meta or {}).get("time_series") if telem else None

    claim_payload = {
        "plot_id": plot_id,
        "farmer_name": plot.farmer_name,
        "crop_type": plot.crop_type,
        "taluk": plot.taluk,
        "area_acres": plot.area_acres,
        "centroid_lat": plot.centroid_lat,
        "centroid_lon": plot.centroid_lon,
        "satellite": {
            "ndvi": plot.ndvi or 0.0,
            "ndmi": plot.ndmi or 0.0,
            "ndre": plot.ndre or 0.0,
            "scene_date": telem.scene_date if telem else "2026-10-30",
            "cloud_cover_pct": telem.cloud_cover_pct if telem else 0.0,
            "data_source": telem.data_source if telem else "database",
        },
        "drought": drought.model_dump(),
        "hydromet": {
            "et0_mm_day": et0,
            "precipitation_mm": precip,
            "soil_moisture_0_7cm_pct": soil_m,
            "survival_liters": v_surv,
            "deficit_mm": round(max(0.0, et0 - precip / 7.0), 3),
        },
        "time_series": ts_meta or {},
    }

    pdf_path, pdf_sha256 = generate_pmfby_pdf(
        payload=claim_payload,
        output_dir=settings.PDF_OUTPUT_DIR,
        verify_base_url=base_url,
    )
    pdf_size = Path(pdf_path).stat().st_size if Path(pdf_path).exists() else 0
    now_dt = datetime.utcnow()

    hash_res = await db.execute(
        select(ClaimDossier).where(ClaimDossier.sha256_hash == pdf_sha256)
    )
    dossier_row = hash_res.scalar_one_or_none()
    if dossier_row is None:
        dossier_row = ClaimDossier(
            plot_id=plot_id,
            pdf_path=pdf_path,
            sha256_hash=pdf_sha256,
            pdf_size_bytes=pdf_size,
            claim_payload=claim_payload,
            is_verified=True,
            verified_at=now_dt,
        )
        db.add(dossier_row)
    else:
        dossier_row.pdf_path = pdf_path
        dossier_row.pdf_size_bytes = pdf_size
        dossier_row.is_verified = True
        dossier_row.verified_at = now_dt
    await db.flush()

    return GenerateDossierResponse(
        plot_id=plot_id,
        farmer_name=plot.farmer_name,
        sha256_hash=pdf_sha256,
        pdf_download_url=f"{base_url}/api/pdf/{Path(pdf_path).name}",
        pdf_size_bytes=pdf_size,
        is_verified=True,
        generated_at=dossier_row.generated_at.isoformat(),
        verified_at=now_dt.isoformat(),
        message="PMFBY Audit Dossier generated and SHA-256 verified.",
    )


@app.get("/api/pdf/{filename}", tags=["Files"])
async def download_pdf(filename: str):
    """Download a generated PMFBY PDF dossier."""
    # Sanitise filename – no path traversal
    safe_name = Path(filename).name
    pdf_path = Path(settings.PDF_OUTPUT_DIR) / safe_name
    if not pdf_path.exists() or not str(pdf_path).startswith(
        str(Path(settings.PDF_OUTPUT_DIR))
    ):
        raise HTTPException(status_code=404, detail="PDF not found.")
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=safe_name,
    )


# ── Static frontend ────────────────────────────────────────────────────────────
_frontend_dir = Path(__file__).parent.parent / "frontend"
if _frontend_dir.exists():
    app.mount(
        "/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend"
    )
