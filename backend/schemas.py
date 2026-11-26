"""
SookshmaJal – Pydantic request/response schemas.
Includes Karnataka geo-fence validation and strict polygon bounds checks.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# ── Karnataka bounding box ─────────────────────────────────────────────────────
# Approx: lat 11.5–18.5 N, lon 74.0–78.5 E
_KA_LAT_MIN, _KA_LAT_MAX = 11.5, 18.5
_KA_LON_MIN, _KA_LON_MAX = 74.0, 78.5

# Tumakuru district approximate bounds (tighter)
_TUM_LAT_MIN, _TUM_LAT_MAX = 12.5, 14.5
_TUM_LON_MIN, _TUM_LON_MAX = 76.0, 77.8


def _validate_karnataka_coords(coords: list[list[float]]) -> list[list[float]]:
    """Ensure every coordinate in a ring lies within Karnataka bounds."""
    for lon, lat in coords:
        if not (_KA_LAT_MIN <= lat <= _KA_LAT_MAX):
            raise ValueError(
                f"Latitude {lat} is outside Karnataka bounds "
                f"({_KA_LAT_MIN}–{_KA_LAT_MAX})"
            )
        if not (_KA_LON_MIN <= lon <= _KA_LON_MAX):
            raise ValueError(
                f"Longitude {lon} is outside Karnataka bounds "
                f"({_KA_LON_MIN}–{_KA_LON_MAX})"
            )
    return coords


# ── Request schemas ────────────────────────────────────────────────────────────


class PolygonCoord(BaseModel):
    """A single [lon, lat] pair."""

    lon: float = Field(..., ge=_KA_LON_MIN, le=_KA_LON_MAX, description="Longitude (E)")
    lat: float = Field(..., ge=_KA_LAT_MIN, le=_KA_LAT_MAX, description="Latitude (N)")


class AnalyzePlotRequest(BaseModel):
    """
    POST /api/analyze-plot request body.
    polygon_coordinates: list of [lon, lat] pairs forming a closed ring.
    """

    farmer_name: str = Field(
        "Tumakuru Farmer", min_length=2, max_length=255
    )
    phone_number: str | None = Field(None, max_length=30)
    crop_type: str = Field(..., min_length=2, max_length=100)
    taluk: str | None = Field(
        None,
        description="Karnataka taluk (Madhugiri, Koratagere, Chikkanayakanahalli, Challakere, Bagepalli, etc.)",
    )
    hobli: str | None = Field(None, max_length=100, description="Optional revenue hobli")
    village: str | None = Field(None, max_length=100, description="Optional revenue village")
    survey_no: str | None = Field(None, max_length=50, description="Optional Bhoomi survey number")
    area_acres: float = Field(
        ..., ge=0.1, le=50.0, description="Plot area in acres (0.1–50)"
    )
    irrigation_source: str | None = Field(
        None, max_length=50, description="Purely Rain-Fed, Borewell, or Canal/Tank"
    )
    observed_symptoms: list[str] = Field(
        default_factory=list, description="Field symptoms observed by farmer"
    )
    photo_base64: str | None = Field(
        None, description="Optional base64-encoded geotagged field photo"
    )
    photo_filename: str | None = Field(None, max_length=120)
    photo_lat: float | None = Field(None, ge=-90.0, le=90.0)
    photo_lon: float | None = Field(None, ge=-180.0, le=180.0)
    photo_timestamp: str | None = Field(None, max_length=64)
    allow_missing_gps: bool = Field(
        True,
        description="When false, rejects photo submissions that lack GPS coordinates.",
    )
    polygon_coordinates: list[list[float]] = Field(
        ...,
        min_length=4,
        description="Closed GeoJSON ring: list of [lon, lat] pairs, first == last",
    )
    use_fallback: bool = Field(False, description="Force offline fallback cache")

    @field_validator("polygon_coordinates")
    @classmethod
    def validate_polygon(cls, v: list[list[float]]) -> list[list[float]]:
        if len(v) < 4:
            raise ValueError(
                "Polygon must have at least 4 coordinate pairs (closed ring)."
            )
        for pair in v:
            if len(pair) != 2:
                raise ValueError("Each coordinate must be [lon, lat].")
        # Closure check
        if v[0] != v[-1]:
            v = v + [v[0]]
        _validate_karnataka_coords(v)
        return v

    @field_validator("farmer_name", mode="before")
    @classmethod
    def default_farmer_name(cls, v: Any) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "Tumakuru Farmer"
        return str(v).strip()

    @field_validator("taluk")
    @classmethod
    def validate_taluk(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        aliases = {
            "C.N. Halli": "Chikkanayakanahalli",
            "CN Halli": "Chikkanayakanahalli",
        }
        return aliases.get(v, v)

    def to_geojson_polygon(self) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [self.polygon_coordinates],
            },
            "properties": {"farmer": self.farmer_name, "crop": self.crop_type},
        }


# ── Response sub-schemas ───────────────────────────────────────────────────────


class SatelliteIndices(BaseModel):
    ndvi: float = Field(
        ..., description="Normalized Difference Vegetation Index (-1 to 1)"
    )
    ndmi: float = Field(
        ..., description="Normalized Difference Moisture Index (-1 to 1)"
    )
    ndre: float = Field(..., description="Normalized Difference Red-Edge (-1 to 1)")
    scene_date: str
    cloud_cover_pct: float
    data_source: str = "planetary_computer"


class DroughtAssessment(BaseModel):
    stage: Literal["healthy", "early_stress", "moderate_drought", "severe_drought"]
    stage_label: str
    color_token: str  # e.g. "color-2", "color-5", "color-3"
    ndmi_threshold: float
    ndvi_threshold: float
    recommendation_en: str
    recommendation_kn: str  # Kannada


class HydrometData(BaseModel):
    et0_mm_day: float = Field(..., description="FAO-56 Reference ET₀ (mm/day)")
    precipitation_mm: float = Field(..., description="Last 7-day precipitation (mm)")
    soil_moisture_0_7cm_pct: float = Field(
        ..., description="0–7 cm volumetric soil moisture (%)"
    )
    survival_liters: float = Field(
        ..., description="V_surv: minimum water needed for crop survival (litres)"
    )
    deficit_mm: float = Field(
        ..., description="ET₀ – precipitation water deficit (mm/day)"
    )
    open_meteo_timestamp: str


class TimeSeriesData(BaseModel):
    dates: list[str] = Field(default_factory=list)
    ndvi: list[float] = Field(default_factory=list)
    ndmi: list[float] = Field(default_factory=list)
    ndre: list[float] = Field(default_factory=list)
    baseline_ndvi: list[float] = Field(default_factory=list)
    soil_moisture: list[float] = Field(default_factory=list)
    et0: list[float] = Field(default_factory=list)
    stress_onset_date: str | None = None
    stress_onset_index: int | None = None
    days_since_stress_onset: int | None = None
    data_source: str = "sentinel2_openmeteo"


class CropIrrigationGuidance(BaseModel):
    crop_type: str
    critical_window: str
    daily_survival_liters: float
    borewell_advisory: str
    irrigation_schedule: str


class AnalyzePlotResponse(BaseModel):
    plot_id: str
    farmer_name: str
    phone_number: str | None = None
    district: str = "Tumakuru"
    taluk: str
    hobli: str | None = None
    village: str | None = None
    survey_no: str | None = None
    crop_type: str
    area_acres: float
    irrigation_source: str | None = None
    observed_symptoms: list[str] = Field(default_factory=list)
    pmfby_eligible: str = "NOT ELIGIBLE — Normal Moisture"
    photo_sha256: str | None = None
    photo_url: str | None = None
    photo_lat: float | None = None
    photo_lon: float | None = None
    photo_timestamp: str | None = None
    geolock_status: str = "MISSING_GPS"
    region_match: bool = False
    distance_km: float | None = None
    geolock_distance_km: float | None = None
    photo_attached: bool = False
    centroid_lat: float
    centroid_lon: float
    satellite: SatelliteIndices
    drought: DroughtAssessment
    hydromet: HydrometData
    time_series: TimeSeriesData = Field(default_factory=TimeSeriesData)
    irrigation_guidance: CropIrrigationGuidance | None = None
    audio_base64: str | None = None
    audio_mime: str = "text/plain"
    audio_source: str = "text_only"
    pdf_sha256: str | None = None
    pdf_download_url: str | None = None
    dossier_id: str | None = None
    entry_source: str = "Live Farmer Entry"
    audit_status: str = "PENDING"
    officer_remark: str | None = None
    reviewed_at: str | None = None
    analysed_at: str


class GenerateDossierResponse(BaseModel):
    plot_id: str
    farmer_name: str
    sha256_hash: str
    pdf_download_url: str
    pdf_size_bytes: int
    is_verified: bool
    generated_at: str
    verified_at: str | None = None
    message: str


class PlotSummary(BaseModel):
    plot_id: str
    farmer_name: str
    taluk: str
    village: str | None = None
    survey_no: str | None = None
    crop_type: str
    area_acres: float
    drought_stage: str | None
    ndvi: float | None
    ndmi: float | None
    photo_url: str | None = None
    photo_sha256: str | None = None
    photo_lat: float | None = None
    photo_lon: float | None = None
    geolock_status: str = "MISSING_GPS"
    photo_attached: bool = False
    dossier_id: str | None = None
    dossier_id: str | None = None
    dossier_hash: str | None = None
    pdf_download_url: str | None = None
    entry_source: str = "Live Farmer Entry"
    audit_status: str = "PENDING"
    officer_remark: str | None = None
    reviewed_at: str | None = None
    created_at: str


class PlotsListResponse(BaseModel):
    total: int
    plots: list[PlotSummary]


class RegionalPlotItem(BaseModel):
    plot_id: str
    farmer_name: str
    phone_number: str | None = None
    district: str = "Tumakuru"
    taluk: str
    hobli: str | None = None
    village: str | None = None
    survey_no: str | None = None
    crop_type: str
    area_acres: float
    irrigation_source: str | None = None
    observed_symptoms: list[str] = Field(default_factory=list)
    pmfby_eligible: str | None = None
    photo_sha256: str | None = None
    photo_url: str | None = None
    photo_lat: float | None = None
    photo_lon: float | None = None
    photo_timestamp: str | None = None
    geolock_status: str = "MISSING_GPS"
    region_match: bool = False
    distance_km: float | None = None
    geolock_distance_km: float | None = None
    photo_attached: bool = False
    centroid_lat: float
    centroid_lon: float
    polygon_coordinates: list[list[float]] = Field(default_factory=list)
    ndvi: float | None = None
    ndmi: float | None = None
    ndre: float | None = None
    drought_stage: str | None = None
    survival_liters: float | None = None
    et0_mm_day: float | None = None
    precipitation_mm: float | None = None
    soil_moisture_0_7cm_pct: float | None = None
    scene_date: str | None = None
    data_source: str = "database"
    created_at: str
    dossier_id: str | None = None
    dossier_hash: str | None = None
    pdf_download_url: str | None = None
    entry_source: str = "Live Farmer Entry"
    audit_status: str = "PENDING"
    officer_remark: str | None = None
    reviewed_at: str | None = None
    is_verified: bool = False
    time_series: TimeSeriesData = Field(default_factory=TimeSeriesData)


class RegionalSummaryResponse(BaseModel):
    taluk: str
    total_plots: int
    total_acres: float
    severe_count: int
    moderate_count: int
    normal_count: int
    ready_for_audit_count: int
    plots: list[RegionalPlotItem]


class CadastralVillageSummary(BaseModel):
    district: str = "Tumakuru"
    taluk: str
    hobli: str
    village: str
    survey_numbers: list[str]


class CadastralVillagesResponse(BaseModel):
    taluk: str
    villages: list[CadastralVillageSummary]


class CadastralParcelResponse(BaseModel):
    district: str = "Tumakuru"
    taluk: str
    hobli: str
    village: str
    survey_no: str
    acres: float
    soil_type: str
    default_crop: str
    coordinates: list[list[float]]
    geojson: dict[str, Any]


class OfficerLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=255)


class OfficerLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    officer_email: str
    expires_in_seconds: int


class AuditDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "DISAPPROVED", "PENDING"]
    officer_remark: str | None = Field(default=None, max_length=300)


class AuditDecisionResponse(BaseModel):
    plot_id: str
    audit_status: str
    officer_remark: str | None = None
    reviewed_at: str | None = None
    message: str


class VerifyDossierResponse(BaseModel):
    sha256_hash: str
    is_valid: bool
    plot_id: str | None
    farmer_name: str | None
    generated_at: str | None
    claim_payload: dict | None = None
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    team: str = "VECTORZZ"
    hackathon: str = "Hackwarts 2026"
    timestamp: str
