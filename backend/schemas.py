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

    farmer_name: str = Field(..., min_length=2, max_length=255)
    crop_type: str = Field(..., min_length=2, max_length=100)
    taluk: str = Field(
        ...,
        description="Tumakuru taluk (Madhugiri, Koratagere, Chikkanayakanahalli, etc.)",
    )
    area_acres: float = Field(
        ..., ge=0.1, le=50.0, description="Plot area in acres (0.1–50)"
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

    @field_validator("taluk")
    @classmethod
    def validate_taluk(cls, v: str) -> str:
        known = {
            "Madhugiri",
            "Koratagere",
            "Chikkanayakanahalli",
            "Tumakuru",
            "Pavagada",
            "Tiptur",
            "Turuvekere",
            "Kunigal",
            "Sira",
            "Gubbi",
        }
        if v not in known:
            # Allow any taluk but warn; don't reject
            pass
        return v

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
    taluk: str
    crop_type: str
    area_acres: float
    centroid_lat: float
    centroid_lon: float
    satellite: SatelliteIndices
    drought: DroughtAssessment
    hydromet: HydrometData
    time_series: TimeSeriesData = Field(default_factory=TimeSeriesData)
    irrigation_guidance: CropIrrigationGuidance | None = None
    audio_base64: str | None = None  # Sarvam TTS Kannada advisory or WAV fallback
    audio_mime: str = "audio/wav"
    audio_source: str = "offline_wav_fallback"
    pdf_sha256: str | None = None
    pdf_download_url: str | None = None
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
    crop_type: str
    area_acres: float
    drought_stage: str | None
    ndvi: float | None
    ndmi: float | None
    created_at: str


class PlotsListResponse(BaseModel):
    total: int
    plots: list[PlotSummary]


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
