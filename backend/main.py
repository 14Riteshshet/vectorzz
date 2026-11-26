"""
SookshmaJal – FastAPI application entry point.
Routes:
  GET  /health                        – liveness probe
  POST /api/analyze-plot              – full satellite + hydromet analysis
  GET  /api/verify/{sha256_hash}      – PMFBY dossier hash verification
  GET  /api/plots                     – list all saved plots
  Static mount at /                   – serves frontend/
"""

import base64
import hashlib
import hmac
import io
import json
import logging
import math
import time
import uuid as _uuid_mod
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    CadastralParcelResponse,
    CadastralVillagesResponse,
    CadastralVillageSummary,
    CropIrrigationGuidance,
    DroughtAssessment,
    GenerateDossierResponse,
    HealthResponse,
    HydrometData,
    OfficerLoginRequest,
    OfficerLoginResponse,
    PlotsListResponse,
    PlotSummary,
    RegionalPlotItem,
    RegionalSummaryResponse,
    SatelliteIndices,
    TimeSeriesData,
    VerifyDossierResponse,
)
from backend.tts import build_kannada_advisory_text, generate_voice_advisory

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
    Path(settings.PHOTO_UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("Ready. Team VECTORZZ · Hackwarts 2026 🌱")
    yield
    logger.info("SookshmaJal shutting down.")


DbSession = Annotated[AsyncSession, Depends(get_db)]
_bearer_scheme = HTTPBearer(auto_error=False)
_OFFICER_TOKEN_TTL_SEC = 86400


def _create_officer_token(username: str) -> str:
    payload_dict = {"sub": username, "exp": int(time.time()) + _OFFICER_TOKEN_TTL_SEC}
    payload_b64 = (
        base64.urlsafe_b64encode(json.dumps(payload_dict).encode("utf-8"))
        .decode("ascii")
        .rstrip("=")
    )
    sig = hmac.new(
        settings.OFFICER_SECRET_KEY.encode("utf-8"),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")
    return f"{payload_b64}.{sig_b64}"


def _verify_officer_token(token: str) -> str | None:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        expected_sig = hmac.new(
            settings.OFFICER_SECRET_KEY.encode("utf-8"),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).digest()
        expected_b64 = (
            base64.urlsafe_b64encode(expected_sig).decode("ascii").rstrip("=")
        )
        if not hmac.compare_digest(sig_b64, expected_b64):
            return None
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        if int(data.get("exp", 0)) < int(time.time()):
            return None
        return data.get("sub")
    except Exception:
        return None


async def require_officer(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer_scheme)],
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Officer authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    officer_sub = _verify_officer_token(credentials.credentials)
    if not officer_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired officer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return officer_sub


OfficerUser = Annotated[str, Depends(require_officer)]


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


# ── Centroid & Taluk helpers ───────────────────────────────────────────────────
def _compute_centroid(coords: list[list[float]]) -> tuple[float, float]:
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lons) / len(lons), sum(lats) / len(lats)


_TALUK_TO_DISTRICT = {
    "Madhugiri": "Tumakuru",
    "Koratagere": "Tumakuru",
    "Chikkanayakanahalli": "Tumakuru",
    "Pavagada": "Tumakuru",
    "Sira": "Tumakuru",
    "Tumakuru": "Tumakuru",
    "Gubbi": "Tumakuru",
    "Tiptur": "Tumakuru",
    "Turuvekere": "Tumakuru",
    "Kunigal": "Tumakuru",
    "Challakere": "Chitradurga",
    "Hiriyur": "Chitradurga",
    "Bagepalli": "Chikkaballapur",
    "Kalaburagi": "Kalaburagi",
    "Vijayapura": "Vijayapura",
}


def _infer_taluk_from_coords(lat: float, lon: float) -> str:
    """Infer Karnataka taluk from plot centroid coordinates."""
    if lat >= 17.0:
        return "Kalaburagi"
    if lat >= 16.5:
        return "Vijayapura"
    if lat >= 14.2 and lon < 76.9:
        return "Challakere"
    if lat >= 14.0 and lon >= 77.15:
        return "Pavagada"
    if lon >= 77.5:
        return "Bagepalli"
    if lon < 77.05:
        return "Chikkanayakanahalli"
    if lat >= 13.60:
        return "Madhugiri"
    if lat >= 13.45:
        return "Koratagere"
    return "Tumakuru"


def _compute_pmfby_eligibility(stage: str) -> str:
    if stage == "severe_drought":
        return "ELIGIBLE — Severe Moisture Deficit"
    if stage in ("moderate_drought", "early_stress"):
        return "WATCHLIST — Moderate Stress"
    return "NOT ELIGIBLE — Normal Moisture"


_TALUK_BOUNDS = {
    "Madhugiri": (13.48, 13.85, 77.05, 77.38),
    "Koratagere": (13.38, 13.68, 77.08, 77.38),
    "Chikkanayakanahalli": (13.25, 13.62, 76.72, 77.08),
    "Pavagada": (13.90, 14.30, 77.10, 77.50),
    "Sira": (13.55, 13.95, 76.75, 77.12),
    "Tumakuru": (13.18, 13.50, 76.95, 77.28),
    "Gubbi": (13.15, 13.50, 76.78, 77.08),
    "Tiptur": (13.12, 13.42, 76.35, 76.68),
    "Turuvekere": (13.02, 13.32, 76.52, 76.85),
    "Kunigal": (12.88, 13.20, 76.88, 77.20),
    "Challakere": (14.12, 14.52, 76.48, 76.88),
    "Hiriyur": (13.78, 14.15, 76.45, 76.82),
    "Bagepalli": (13.62, 13.96, 77.62, 78.00),
    "Kalaburagi": (17.15, 17.55, 76.65, 77.05),
    "Vijayapura": (16.65, 17.05, 75.52, 75.92),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers between two lat/lon points."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a)), 2)


def _dms_to_deg(dms: object, ref: object) -> float | None:
    try:
        vals = []
        for part in dms:  # type: ignore[union-attr]
            if isinstance(part, tuple) and len(part) == 2:
                vals.append(float(part[0]) / float(part[1] or 1))
            else:
                vals.append(float(part))
        if len(vals) != 3:
            return None
        deg = vals[0] + vals[1] / 60.0 + vals[2] / 3600.0
        if ref and str(ref).strip().upper() in ("S", "W"):
            deg = -deg
        return round(deg, 6)
    except Exception:
        return None


def _extract_exif_gps(
    img_bytes: bytes,
) -> tuple[float | None, float | None, str | None]:
    """Extract decimal (lat, lon, datetime_str) from image EXIF GPS tags if present."""
    try:
        from PIL import Image as PILImage
        from PIL.ExifTags import GPSTAGS

        with PILImage.open(io.BytesIO(img_bytes)) as img:
            exif = img.getexif()
            if not exif:
                return None, None, None
            exif_ts = exif.get(36867) or exif.get(306)
            gps_ifd = exif.get_ifd(0x8825)
            if not gps_ifd:
                return None, None, str(exif_ts) if exif_ts else None
            gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
            lat = _dms_to_deg(gps.get("GPSLatitude"), gps.get("GPSLatitudeRef"))
            lon = _dms_to_deg(gps.get("GPSLongitude"), gps.get("GPSLongitudeRef"))
            return lat, lon, str(exif_ts) if exif_ts else None
    except Exception:
        return None, None, None


def _evaluate_photo_geolock(
    photo_lat: float | None,
    photo_lon: float | None,
    plot_lat: float,
    plot_lon: float,
    taluk: str,
) -> tuple[str, bool, float | None]:
    """
    Validate photo GPS against the plot centroid and selected taluk bounds.
    Returns (geolock_status, region_match, distance_km).
    """
    if photo_lat is None or photo_lon is None:
        return "MISSING_GPS", False, None

    dist_km = _haversine_km(photo_lat, photo_lon, plot_lat, plot_lon)

    if dist_km <= 5.0:
        return "VERIFIED_IN_REGION", True, dist_km
    if dist_km <= 35.0:
        return "DISTRICT_MATCH_NEARBY", True, dist_km
    return "OUTSIDE_REGION_WARNING", False, dist_km


def _save_uploaded_photo(
    plot_id: str,
    photo_base64: str,
    filename: str | None = None,
) -> tuple[str, str, float | None, float | None, str | None]:
    """Decode base64 photo, extract EXIF GPS, write to PHOTO_UPLOAD_DIR."""
    raw_b64 = photo_base64.strip()
    ext = "jpg"
    if raw_b64.startswith("data:") and "," in raw_b64:
        header, raw_b64 = raw_b64.split(",", 1)
        if "png" in header.lower():
            ext = "png"
        elif "webp" in header.lower():
            ext = "webp"
    elif filename:
        cand = Path(filename).suffix.lstrip(".").lower()
        if cand in {"jpg", "jpeg", "png", "webp"}:
            ext = "jpg" if cand == "jpeg" else cand

    try:
        img_bytes = base64.b64decode(raw_b64, validate=False)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid photo base64 payload.") from exc

    if not img_bytes or len(img_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=422, detail="Photo must be non-empty and under 10 MB."
        )

    exif_lat, exif_lon, exif_ts = _extract_exif_gps(img_bytes)
    photo_sha256 = hashlib.sha256(img_bytes).hexdigest()
    upload_dir = Path(settings.PHOTO_UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    out_path = upload_dir / f"{plot_id}.{ext}"
    out_path.write_bytes(img_bytes)
    return str(out_path), photo_sha256, exif_lat, exif_lon, exif_ts


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


@app.post(
    "/api/officer/login",
    response_model=OfficerLoginResponse,
    tags=["Auth"],
)
async def officer_login(body: OfficerLoginRequest):
    """Authenticate a Regional Agricultural / PMFBY Officer and return a signed bearer token."""
    user_ok = hmac.compare_digest(body.username.strip(), settings.OFFICER_USERNAME)
    pass_ok = hmac.compare_digest(body.password, settings.OFFICER_PASSWORD)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid officer username or password.",
        )
    token = _create_officer_token(settings.OFFICER_USERNAME)
    return OfficerLoginResponse(
        access_token=token,
        token_type="bearer",
        officer_email=settings.OFFICER_USERNAME,
        expires_in_seconds=_OFFICER_TOKEN_TTL_SEC,
    )


@app.post("/api/analyze-plot", response_model=AnalyzePlotResponse, tags=["Analysis"])
@app.post("/api/analyse", response_model=AnalyzePlotResponse, tags=["Analysis"], include_in_schema=False)
@app.post("/api/analyze", response_model=AnalyzePlotResponse, tags=["Analysis"], include_in_schema=False)
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
    - Generates Kannada advisory text and spoken gTTS MP3 audio (with browser TTS fallback)
    - Generates PMFBY PDF dossier with SHA-256 hash + QR code
    - Persists FarmPlot, TelemetryLog, ClaimDossier records
    """
    lon_c, lat_c = _compute_centroid(body.polygon_coordinates)
    effective_taluk = (
        body.taluk.strip()
        if body.taluk and body.taluk.strip()
        else _infer_taluk_from_coords(lat_c, lon_c)
    )
    taluk_key = effective_taluk.lower().replace(" ", "")
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
    district = _TALUK_TO_DISTRICT.get(effective_taluk, "Tumakuru")
    pmfby_eligible = _compute_pmfby_eligibility(drought.stage)
    base_url = str(request.base_url).rstrip("/")

    photo_path: str | None = None
    photo_sha256: str | None = None
    photo_url: str | None = None
    eff_photo_lat = body.photo_lat
    eff_photo_lon = body.photo_lon
    eff_photo_ts = body.photo_timestamp

    if body.photo_base64:
        photo_path, photo_sha256, exif_lat, exif_lon, exif_ts = _save_uploaded_photo(
            plot_id, body.photo_base64, body.photo_filename
        )
        photo_url = f"{base_url}/api/photos/{Path(photo_path).name}"
        if eff_photo_lat is None and exif_lat is not None:
            eff_photo_lat = exif_lat
        if eff_photo_lon is None and exif_lon is not None:
            eff_photo_lon = exif_lon
        if not eff_photo_ts and exif_ts:
            eff_photo_ts = exif_ts

    geolock_status, region_match, distance_km = _evaluate_photo_geolock(
        eff_photo_lat, eff_photo_lon, lat_c, lon_c, effective_taluk
    )
    if not body.allow_missing_gps and geolock_status == "MISSING_GPS":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Photo GPS coordinates are required when allow_missing_gps is false.",
        )

    db_plot = FarmPlot(
        id=plot_id,
        farmer_name=body.farmer_name,
        phone_number=body.phone_number,
        district=district,
        taluk=effective_taluk,
        hobli=body.hobli,
        village=body.village,
        survey_no=body.survey_no,
        crop_type=body.crop_type,
        area_acres=body.area_acres,
        irrigation_source=body.irrigation_source,
        observed_symptoms=body.observed_symptoms,
        photo_path=photo_path,
        photo_sha256=photo_sha256,
        photo_lat=eff_photo_lat,
        photo_lon=eff_photo_lon,
        photo_timestamp=eff_photo_ts,
        geolock_status=geolock_status,
        region_match=region_match,
        distance_km=distance_km,
        pmfby_eligible=pmfby_eligible,
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

    # ── 5. Kannada Crop Water Advisory (text-only) ──────────────────────────
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

    audio_mime = "text/plain"
    audio_source = "text_only"

    # ── 6. PMFBY PDF ─────────────────────────────────────────────────────────
    pdf_sha256: Optional[str] = None
    pdf_download_url: Optional[str] = None
    dossier_id: Optional[str] = None

    sat_payload = {k: v for k, v in sat_raw.items() if k != "time_series"}
    claim_payload = {
        "plot_id": plot_id,
        "farmer_name": body.farmer_name,
        "phone_number": body.phone_number,
        "crop_type": body.crop_type,
        "district": district,
        "taluk": effective_taluk,
        "hobli": body.hobli,
        "village": body.village,
        "survey_no": body.survey_no,
        "area_acres": body.area_acres,
        "irrigation_source": body.irrigation_source,
        "observed_symptoms": body.observed_symptoms,
        "pmfby_eligible": pmfby_eligible,
        "photo_sha256": photo_sha256,
        "photo_lat": eff_photo_lat,
        "photo_lon": eff_photo_lon,
        "photo_timestamp": eff_photo_ts,
        "photo_path": photo_path,
        "geolock_status": geolock_status,
        "region_match": region_match,
        "distance_km": distance_km,
        "centroid_lat": lat_c,
        "centroid_lon": lon_c,
        "satellite": sat_payload,
        "drought": drought.model_dump(),
        "hydromet": hm_raw,
        "time_series": ts_raw,
    }

    try:
        pdf_path, pdf_sha256 = generate_pmfby_pdf(
            payload=claim_payload,
            output_dir=settings.PDF_OUTPUT_DIR,
            verify_base_url=base_url,
        )
        pdf_download_url = f"{base_url}/api/pdf/{Path(pdf_path).name}"

        stored_claim_payload = {k: v for k, v in claim_payload.items() if k != "photo_path"}
        pdf_size = Path(pdf_path).stat().st_size if Path(pdf_path).exists() else 0
        async with db.begin_nested():
            db_claim = ClaimDossier(
                plot_id=plot_id,
                pdf_path=pdf_path,
                sha256_hash=pdf_sha256,
                pdf_size_bytes=pdf_size,
                claim_payload=stored_claim_payload,
                is_verified=True,
                verified_at=datetime.utcnow(),
            )
            db.add(db_claim)
            await db.flush()
            dossier_id = db_claim.id

    except Exception as exc:
        logger.warning("PDF generation failed (non-fatal): %s", exc)

    analysed_at = datetime.now(timezone.utc).isoformat()

    return AnalyzePlotResponse(
        plot_id=plot_id,
        farmer_name=body.farmer_name,
        phone_number=body.phone_number,
        district=district,
        taluk=effective_taluk,
        hobli=body.hobli,
        village=body.village,
        survey_no=body.survey_no,
        crop_type=body.crop_type,
        area_acres=body.area_acres,
        irrigation_source=body.irrigation_source,
        observed_symptoms=body.observed_symptoms,
        pmfby_eligible=pmfby_eligible,
        photo_sha256=photo_sha256,
        photo_url=photo_url,
        photo_lat=eff_photo_lat,
        photo_lon=eff_photo_lon,
        photo_timestamp=eff_photo_ts,
        geolock_status=geolock_status,
        region_match=region_match,
        distance_km=distance_km,
        geolock_distance_km=distance_km,
        photo_attached=bool(photo_path),
        centroid_lat=lat_c,
        centroid_lon=lon_c,
        satellite=sat_indices,
        drought=drought,
        hydromet=hydromet_data,
        time_series=time_series,
        irrigation_guidance=irrigation_guidance,
        audio_base64=audio_b64,
        audio_mime=audio_mime,
        audio_source=audio_source,
        pdf_sha256=pdf_sha256,
        pdf_download_url=pdf_download_url,
        dossier_id=dossier_id,
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
async def list_plots(request: Request, db: DbSession):
    """Return a summary list of all analysed farm plots."""
    stmt = (
        select(FarmPlot)
        .options(selectinload(FarmPlot.claim_dossiers))
        .order_by(FarmPlot.created_at.desc())
        .limit(100)
    )
    result = await db.execute(stmt)
    plots = result.scalars().all()
    base_url = str(request.base_url).rstrip("/")

    summaries = []
    for p in plots:
        latest_dossier = (
            max(p.claim_dossiers, key=lambda d: d.generated_at)
            if p.claim_dossiers
            else None
        )
        photo_url = (
            f"{base_url}/api/photos/{Path(p.photo_path).name}"
            if p.photo_path
            else None
        )
        pdf_url = (
            f"{base_url}/api/pdf/{Path(latest_dossier.pdf_path).name}"
            if latest_dossier and latest_dossier.pdf_path
            else None
        )
        summaries.append(
            PlotSummary(
                plot_id=p.id,
                farmer_name=p.farmer_name,
                taluk=p.taluk,
                village=p.village,
                survey_no=p.survey_no,
                crop_type=p.crop_type,
                area_acres=p.area_acres,
                drought_stage=p.drought_stage,
                ndvi=p.ndvi,
                ndmi=p.ndmi,
                photo_url=photo_url,
                photo_sha256=p.photo_sha256,
                photo_lat=p.photo_lat,
                photo_lon=p.photo_lon,
                geolock_status=p.geolock_status or "MISSING_GPS",
                photo_attached=bool(p.photo_path),
                dossier_id=latest_dossier.id if latest_dossier else None,
                dossier_hash=latest_dossier.sha256_hash if latest_dossier else None,
                pdf_download_url=pdf_url,
                created_at=p.created_at.isoformat(),
            )
        )
    return PlotsListResponse(total=len(summaries), plots=summaries)


@app.get("/api/history", response_model=PlotsListResponse, tags=["Plots"])
async def list_history_protected(
    request: Request, db: DbSession, _officer: OfficerUser
):
    """Protected all-farmers history endpoint for authenticated Regional Officers."""
    return await list_plots(request, db)


def _extract_polygon_coords(polygon_geojson: str) -> list[list[float]]:
    try:
        parsed = json.loads(polygon_geojson)
        coords = parsed.get("geometry", {}).get("coordinates", [[]])[0]
        return coords if isinstance(coords, list) else []
    except (ValueError, TypeError, IndexError):
        return []


@app.get(
    "/api/regional/summary",
    response_model=RegionalSummaryResponse,
    tags=["Regional"],
)
async def regional_summary(
    request: Request,
    db: DbSession,
    _officer: OfficerUser,
    taluk: str = "ALL",
):
    """
    Aggregate regional KPIs and all saved FarmPlot records for the Regional Officer view.
    Requires a valid Officer Bearer token. Supports filtering by taluk or district.
    """
    taluk_clean = (taluk or "ALL").strip()
    stmt = (
        select(FarmPlot)
        .options(
            selectinload(FarmPlot.telemetry_logs),
            selectinload(FarmPlot.claim_dossiers),
        )
        .order_by(FarmPlot.created_at.desc())
    )
    if taluk_clean.upper() != "ALL":
        aliases = {
            "c.n. halli": ["chikkanayakanahalli", "c.n. halli", "cn halli"],
            "cn halli": ["chikkanayakanahalli", "c.n. halli", "cn halli"],
            "chikkanayakanahalli": ["chikkanayakanahalli", "c.n. halli", "cn halli"],
        }
        accepted = aliases.get(taluk_clean.lower(), [taluk_clean.lower()])
        stmt = stmt.where(
            func.lower(FarmPlot.taluk).in_(accepted)
            | func.lower(FarmPlot.district).in_(accepted)
        )

    result = await db.execute(stmt)
    plots = result.scalars().all()

    base_url = str(request.base_url).rstrip("/")
    severe_count = 0
    moderate_count = 0
    normal_count = 0
    ready_for_audit_count = 0
    total_acres = 0.0
    items: list[RegionalPlotItem] = []

    for p in plots:
        total_acres += float(p.area_acres or 0.0)
        stage = p.drought_stage or "healthy"
        if stage == "severe_drought":
            severe_count += 1
            ready_for_audit_count += 1
        elif stage in ("moderate_drought", "early_stress"):
            moderate_count += 1
            if stage == "moderate_drought":
                ready_for_audit_count += 1
        else:
            normal_count += 1

        latest_telem = (
            max(p.telemetry_logs, key=lambda t: t.recorded_at)
            if p.telemetry_logs
            else None
        )
        latest_dossier = (
            max(p.claim_dossiers, key=lambda d: d.generated_at)
            if p.claim_dossiers
            else None
        )

        ts_raw = (
            (latest_telem.extra_meta or {}).get("time_series")
            if latest_telem
            else None
        )
        ts_data = TimeSeriesData(**ts_raw) if isinstance(ts_raw, dict) else TimeSeriesData()

        pdf_url = (
            f"{base_url}/api/pdf/{Path(latest_dossier.pdf_path).name}"
            if latest_dossier and latest_dossier.pdf_path
            else None
        )

        photo_url = (
            f"{base_url}/api/photos/{Path(p.photo_path).name}"
            if p.photo_path
            else None
        )

        items.append(
            RegionalPlotItem(
                plot_id=p.id,
                farmer_name=p.farmer_name,
                phone_number=p.phone_number,
                district=p.district or _TALUK_TO_DISTRICT.get(p.taluk, "Tumakuru"),
                taluk=p.taluk,
                hobli=p.hobli,
                village=p.village,
                survey_no=p.survey_no,
                crop_type=p.crop_type,
                area_acres=p.area_acres,
                irrigation_source=p.irrigation_source,
                observed_symptoms=p.observed_symptoms or [],
                pmfby_eligible=p.pmfby_eligible or _compute_pmfby_eligibility(stage),
                photo_sha256=p.photo_sha256,
                photo_url=photo_url,
                photo_lat=p.photo_lat,
                photo_lon=p.photo_lon,
                photo_timestamp=p.photo_timestamp,
                geolock_status=p.geolock_status or "MISSING_GPS",
                region_match=bool(p.region_match),
                distance_km=p.distance_km,
                geolock_distance_km=p.distance_km,
                photo_attached=bool(p.photo_path),
                centroid_lat=p.centroid_lat,
                centroid_lon=p.centroid_lon,
                polygon_coordinates=_extract_polygon_coords(p.polygon_geojson),
                ndvi=p.ndvi,
                ndmi=p.ndmi,
                ndre=p.ndre,
                drought_stage=p.drought_stage,
                survival_liters=latest_telem.survival_liters if latest_telem else None,
                et0_mm_day=latest_telem.et0_mm_day if latest_telem else None,
                precipitation_mm=latest_telem.precipitation_mm if latest_telem else None,
                soil_moisture_0_7cm_pct=(
                    latest_telem.soil_moisture_pct if latest_telem else None
                ),
                scene_date=latest_telem.scene_date if latest_telem else None,
                data_source=latest_telem.data_source if latest_telem else "database",
                created_at=p.created_at.isoformat(),
                dossier_id=latest_dossier.id if latest_dossier else None,
                dossier_hash=latest_dossier.sha256_hash if latest_dossier else None,
                pdf_download_url=pdf_url,
                is_verified=bool(latest_dossier.is_verified) if latest_dossier else False,
                time_series=ts_data,
            )
        )

    return RegionalSummaryResponse(
        taluk=taluk_clean,
        total_plots=len(items),
        total_acres=round(total_acres, 2),
        severe_count=severe_count,
        moderate_count=moderate_count,
        normal_count=normal_count,
        ready_for_audit_count=ready_for_audit_count,
        plots=items,
    )


@app.post(
    "/api/plots/{plot_id}/dossier",
    response_model=GenerateDossierResponse,
    tags=["Verification"],
)
@app.post(
    "/api/dossier/{plot_id}",
    response_model=GenerateDossierResponse,
    tags=["Verification"],
    include_in_schema=False,
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
        "phone_number": plot.phone_number,
        "crop_type": plot.crop_type,
        "district": plot.district or _TALUK_TO_DISTRICT.get(plot.taluk, "Tumakuru"),
        "taluk": plot.taluk,
        "hobli": plot.hobli,
        "village": plot.village,
        "survey_no": plot.survey_no,
        "area_acres": plot.area_acres,
        "irrigation_source": plot.irrigation_source,
        "observed_symptoms": plot.observed_symptoms or [],
        "pmfby_eligible": plot.pmfby_eligible
        or _compute_pmfby_eligibility(drought.stage),
        "photo_sha256": plot.photo_sha256,
        "photo_lat": plot.photo_lat,
        "photo_lon": plot.photo_lon,
        "photo_timestamp": plot.photo_timestamp,
        "photo_path": plot.photo_path,
        "geolock_status": plot.geolock_status or "MISSING_GPS",
        "region_match": bool(plot.region_match),
        "distance_km": plot.distance_km,
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

    stored_claim_payload = {k: v for k, v in claim_payload.items() if k != "photo_path"}
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
            claim_payload=stored_claim_payload,
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


_CADASTRAL_DATA_PATH = Path(__file__).parent / "data" / "tumakuru_cadastral.json"

_TALUK_ALIASES = {
    "c.n. halli": "Chikkanayakanahalli",
    "cn halli": "Chikkanayakanahalli",
    "chikkanayakanahalli": "Chikkanayakanahalli",
}


@lru_cache(maxsize=1)
def _load_cadastral_parcels() -> list[dict]:
    if not _CADASTRAL_DATA_PATH.exists():
        return []
    with _CADASTRAL_DATA_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("parcels", [])


def _canonical_taluk(taluk: str | None) -> str | None:
    if not taluk or not taluk.strip():
        return None
    t = taluk.strip()
    return _TALUK_ALIASES.get(t.lower(), t)


@app.get(
    "/api/cadastral/villages",
    response_model=CadastralVillagesResponse,
    tags=["Cadastral"],
)
async def list_cadastral_villages(taluk: str | None = None):
    """Return available hoblis, villages, and survey numbers for a Tumakuru taluk."""
    parcels = _load_cadastral_parcels()
    canon_taluk = _canonical_taluk(taluk)
    if canon_taluk and canon_taluk.upper() != "ALL":
        parcels = [p for p in parcels if p["taluk"].lower() == canon_taluk.lower()]

    grouped: dict[tuple[str, str, str, str], list[str]] = {}
    for p in parcels:
        key = (
            p.get("district") or _TALUK_TO_DISTRICT.get(p["taluk"], "Tumakuru"),
            p["taluk"],
            p["hobli"],
            p["village"],
        )
        grouped.setdefault(key, []).append(p["survey_no"])

    villages = [
        CadastralVillageSummary(
            district=d,
            taluk=t,
            hobli=h,
            village=v,
            survey_numbers=surveys,
        )
        for (d, t, h, v), surveys in grouped.items()
    ]
    return CadastralVillagesResponse(taluk=canon_taluk or "ALL", villages=villages)


@app.get(
    "/api/cadastral/parcel",
    response_model=CadastralParcelResponse,
    tags=["Cadastral"],
)
async def get_cadastral_parcel(taluk: str, village: str, survey_no: str):
    """Return a Bhoomi/Dishaank cadastral parcel polygon and metadata."""
    canon_taluk = _canonical_taluk(taluk) or taluk
    parcels = _load_cadastral_parcels()
    match = next(
        (
            p
            for p in parcels
            if p["taluk"].lower() == canon_taluk.lower()
            and p["village"].lower() == village.strip().lower()
            and p["survey_no"].lower() == survey_no.strip().lower()
        ),
        None,
    )
    if match is None:
        raise HTTPException(
            status_code=404,
            detail=f"Survey parcel '{survey_no}' not found in {village}, {canon_taluk}.",
        )

    return CadastralParcelResponse(
        district=match.get("district")
        or _TALUK_TO_DISTRICT.get(match["taluk"], "Tumakuru"),
        taluk=match["taluk"],
        hobli=match["hobli"],
        village=match["village"],
        survey_no=match["survey_no"],
        acres=match["acres"],
        soil_type=match["soil_type"],
        default_crop=match["default_crop"],
        coordinates=match["coordinates"],
        geojson={
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [match["coordinates"]]},
            "properties": {
                "taluk": match["taluk"],
                "hobli": match["hobli"],
                "village": match["village"],
                "survey_no": match["survey_no"],
                "acres": match["acres"],
                "soil_type": match["soil_type"],
            },
        },
    )


@app.get("/api/photos/{filename}", tags=["Files"])
async def get_uploaded_photo(filename: str, _officer: OfficerUser):
    """Serve an uploaded geotagged field photo (protected; requires Officer token)."""
    safe_name = Path(filename).name
    photo_dir = Path(settings.PHOTO_UPLOAD_DIR).resolve()
    photo_path = (photo_dir / safe_name).resolve()
    if not photo_path.exists() or photo_path.parent != photo_dir:
        raise HTTPException(status_code=404, detail="Photo not found.")
    return FileResponse(path=str(photo_path))


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
