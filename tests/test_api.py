"""
SookshmaJal – FastAPI integration tests.
Tests /health, /api/analyze-plot (with mocked satellite & hydromet),
and /api/verify/{sha256_hash}.
Uses httpx AsyncClient via pytest-anyio.
"""
from __future__ import annotations

import json
import math
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app

# ── A valid Karnataka polygon (Madhugiri area) ────────────────────────────────
VALID_POLYGON = [
    [77.1967, 13.6571],
    [77.2067, 13.6571],
    [77.2067, 13.6671],
    [77.1967, 13.6671],
    [77.1967, 13.6571],
]

VALID_PAYLOAD: dict[str, Any] = {
    "farmer_name": "Ramaiah Gowda",
    "crop_type": "Ragi",
    "taluk": "Madhugiri",
    "area_acres": 2.5,
    "polygon_coordinates": VALID_POLYGON,
    "use_fallback": True,
}

MOCK_SAT_DATA = {
    "ndvi": 0.28,
    "ndmi": -0.22,
    "ndre": 0.19,
    "scene_date": "2026-10-15",
    "cloud_cover_pct": 5.0,
    "data_source": "fallback_cache",
}

MOCK_HYDROMET_DATA = {
    "et0_mm_day": 4.8,
    "precipitation_mm": 10.0,
    "soil_moisture_0_7cm_pct": 22.5,
    "survival_liters": 125000.0,
    "deficit_mm": 3.37,
    "open_meteo_timestamp": "2026-10-15T10:00:00+00:00",
    "source": "open_meteo",
}


@pytest.fixture
async def async_client():
    """Provide an async HTTPX client wrapping the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ── /health ───────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_health_ok(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["team"] == "VECTORZZ"
    assert data["hackathon"] == "Hackwarts 2026"
    assert "timestamp" in data
    assert "version" in data


@pytest.mark.anyio
async def test_health_returns_json_content_type(async_client: AsyncClient):
    resp = await async_client.get("/health")
    assert "application/json" in resp.headers.get("content-type", "")


# ── /api/analyze-plot ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_analyze_plot_success(async_client: AsyncClient):
    with (
        patch("backend.main.fetch_sentinel2_indices", return_value=MOCK_SAT_DATA),
        patch("backend.main.get_hydromet_data", return_value=MOCK_HYDROMET_DATA),
        patch("backend.main.generate_voice_advisory", return_value=(None, "ಬರ ಎಚ್ಚರಿಕೆ")),
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/test.pdf", "a" * 64)),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)

    assert resp.status_code == 200, resp.text
    data = resp.json()

    # Required top-level fields
    for field in ["plot_id", "farmer_name", "taluk", "crop_type", "area_acres",
                  "centroid_lat", "centroid_lon", "satellite", "drought",
                  "hydromet", "analysed_at"]:
        assert field in data, f"Missing field: {field}"

    # Satellite indices
    sat = data["satellite"]
    assert math.isclose(sat["ndvi"], 0.28, abs_tol=0.001)
    assert math.isclose(sat["ndmi"], -0.22, abs_tol=0.001)
    assert sat["data_source"] == "fallback_cache"

    # Drought
    drought = data["drought"]
    assert drought["stage"] in ["healthy", "early_stress", "moderate_drought", "severe_drought"]
    assert isinstance(drought["recommendation_en"], str)

    # Hydromet
    hm = data["hydromet"]
    assert hm["et0_mm_day"] > 0
    assert hm["survival_liters"] >= 0


@pytest.mark.anyio
async def test_analyze_plot_missing_fields(async_client: AsyncClient):
    resp = await async_client.post("/api/analyze-plot", json={})
    assert resp.status_code == 422  # Validation error


@pytest.mark.anyio
async def test_analyze_plot_outside_karnataka(async_client: AsyncClient):
    """Polygon in Mumbai (outside Karnataka) should be rejected."""
    payload = {**VALID_PAYLOAD, "polygon_coordinates": [
        [72.8777, 19.0760],
        [72.8877, 19.0760],
        [72.8877, 19.0860],
        [72.8777, 19.0860],
        [72.8777, 19.0760],
    ]}
    resp = await async_client.post("/api/analyze-plot", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_analyze_plot_area_too_large(async_client: AsyncClient):
    """Area > 50 acres should be rejected."""
    payload = {**VALID_PAYLOAD, "area_acres": 100.0}
    resp = await async_client.post("/api/analyze-plot", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_analyze_plot_area_too_small(async_client: AsyncClient):
    """Area < 0.1 acres should be rejected."""
    payload = {**VALID_PAYLOAD, "area_acres": 0.05}
    resp = await async_client.post("/api/analyze-plot", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_analyze_plot_insufficient_polygon(async_client: AsyncClient):
    """Polygon with < 4 points should be rejected."""
    payload = {**VALID_PAYLOAD, "polygon_coordinates": [[77.19, 13.66], [77.20, 13.66]]}
    resp = await async_client.post("/api/analyze-plot", json=payload)
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_analyze_plot_centroid_computed(async_client: AsyncClient):
    """Centroid should be within Karnataka bounds."""
    with (
        patch("backend.main.fetch_sentinel2_indices", return_value=MOCK_SAT_DATA),
        patch("backend.main.get_hydromet_data", return_value=MOCK_HYDROMET_DATA),
        patch("backend.main.generate_voice_advisory", return_value=(None, "")),
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/t.pdf", "b" * 64)),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)

    data = resp.json()
    assert 11.5 <= data["centroid_lat"] <= 18.5
    assert 74.0 <= data["centroid_lon"] <= 78.5


# ── /api/verify/{sha256_hash} ─────────────────────────────────────────────────

@pytest.mark.anyio
async def test_verify_nonexistent_hash(async_client: AsyncClient):
    """A valid but non-existent hash should return is_valid=False."""
    fake_hash = "a" * 64
    resp = await async_client.get(f"/api/verify/{fake_hash}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is False
    assert data["sha256_hash"] == fake_hash


@pytest.mark.anyio
async def test_verify_invalid_hash_format(async_client: AsyncClient):
    """Non-hex hash should return 422."""
    resp = await async_client.get("/api/verify/not-a-valid-hash")
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_verify_short_hash(async_client: AsyncClient):
    """Hash shorter than 64 chars should return 422."""
    resp = await async_client.get("/api/verify/abcdef1234")
    assert resp.status_code == 422


# ── /api/plots ────────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_list_plots_empty(async_client: AsyncClient):
    """Fresh database should return empty plots list."""
    resp = await async_client.get("/api/plots")
    assert resp.status_code == 200
    data = resp.json()
    assert "plots" in data
    assert "total" in data
    assert isinstance(data["plots"], list)
    assert data["total"] >= 0


@pytest.mark.anyio
async def test_list_plots_response_schema(async_client: AsyncClient):
    """Verify plots response has correct schema."""
    resp = await async_client.get("/api/plots")
    data = resp.json()
    assert isinstance(data["total"], int)
    for plot in data.get("plots", []):
        for field in ["plot_id", "farmer_name", "taluk", "crop_type", "area_acres"]:
            assert field in plot


# ── Drought stage classification tests ───────────────────────────────────────

@pytest.mark.anyio
async def test_drought_stage_severe(async_client: AsyncClient):
    """Very negative NDMI and NDVI → severe drought."""
    sat_data = {**MOCK_SAT_DATA, "ndvi": 0.05, "ndmi": -0.55}
    with (
        patch("backend.main.fetch_sentinel2_indices", return_value=sat_data),
        patch("backend.main.get_hydromet_data", return_value=MOCK_HYDROMET_DATA),
        patch("backend.main.generate_voice_advisory", return_value=(None, "")),
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/t.pdf", "c" * 64)),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["drought"]["stage"] == "severe_drought"


@pytest.mark.anyio
async def test_drought_stage_healthy(async_client: AsyncClient):
    """High NDMI and NDVI → healthy."""
    sat_data = {**MOCK_SAT_DATA, "ndvi": 0.70, "ndmi": 0.35}
    with (
        patch("backend.main.fetch_sentinel2_indices", return_value=sat_data),
        patch("backend.main.get_hydromet_data", return_value=MOCK_HYDROMET_DATA),
        patch("backend.main.generate_voice_advisory", return_value=(None, "")),
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/t.pdf", "d" * 64)),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["drought"]["stage"] == "healthy"
