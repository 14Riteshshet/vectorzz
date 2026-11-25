"""
SookshmaJal – FastAPI integration & component tests.
Tests /health, /api/analyze-plot (mocked & offline cache), time-series payload,
PMFBY PDF dossier generation + SHA-256/QR verification, and Kannada gTTS advisory.
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image as PILImage

from backend.config import get_settings
from backend.database import init_db
from backend.main import app
from backend.pdf_gen import generate_pmfby_pdf
from backend.tts import build_kannada_advisory_text, generate_tts_advisory

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


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    """Initialise DB tables and provide an async HTTPX client wrapping FastAPI."""
    await init_db()
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
        patch(
            "backend.main.generate_pmfby_pdf",
            return_value=("/tmp/test.pdf", uuid.uuid4().hex * 2),
        ),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)

    assert resp.status_code == 200, resp.text
    data = resp.json()

    for field in [
        "plot_id",
        "farmer_name",
        "taluk",
        "crop_type",
        "area_acres",
        "centroid_lat",
        "centroid_lon",
        "satellite",
        "drought",
        "hydromet",
        "time_series",
        "irrigation_guidance",
        "analysed_at",
    ]:
        assert field in data, f"Missing field: {field}"

    sat = data["satellite"]
    assert math.isclose(sat["ndvi"], 0.28, abs_tol=0.001)
    assert math.isclose(sat["ndmi"], -0.22, abs_tol=0.001)
    assert sat["data_source"] == "fallback_cache"

    drought = data["drought"]
    assert drought["stage"] in [
        "healthy",
        "early_stress",
        "moderate_drought",
        "severe_drought",
    ]
    assert isinstance(drought["recommendation_en"], str)

    hm = data["hydromet"]
    assert hm["et0_mm_day"] > 0
    assert hm["survival_liters"] >= 0

    ts = data["time_series"]
    for ts_key in [
        "dates",
        "ndvi",
        "ndmi",
        "ndre",
        "baseline_ndvi",
        "soil_moisture",
        "et0",
    ]:
        assert ts_key in ts
        assert len(ts[ts_key]) == len(ts["dates"])
        assert len(ts[ts_key]) >= 5


@pytest.mark.anyio
async def test_analyze_plot_missing_fields(async_client: AsyncClient):
    resp = await async_client.post("/api/analyze-plot", json={})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_analyze_plot_outside_karnataka(async_client: AsyncClient):
    """Polygon in Mumbai (outside Karnataka) should be rejected."""
    payload = {
        **VALID_PAYLOAD,
        "polygon_coordinates": [
            [72.8777, 19.0760],
            [72.8877, 19.0760],
            [72.8877, 19.0860],
            [72.8777, 19.0860],
            [72.8777, 19.0760],
        ],
    }
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
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/t.pdf", uuid.uuid4().hex * 2)),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)

    data = resp.json()
    assert 11.5 <= data["centroid_lat"] <= 18.5
    assert 74.0 <= data["centroid_lon"] <= 78.5


# ── Fallback Cache Loading (3 Tumakuru Taluks) ────────────────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize(
    "taluk,lat,lon,expected_stage,expect_onset",
    [
        ("Madhugiri", 13.6621, 77.2017, "severe_drought", True),
        ("Koratagere", 13.5225, 77.2365, "moderate_drought", True),
        ("Chikkanayakanahalli", 13.4318, 76.9336, "healthy", False),
    ],
)
async def test_fallback_cache_taluk_trajectories(
    async_client: AsyncClient,
    taluk: str,
    lat: float,
    lon: float,
    expected_stage: str,
    expect_onset: bool,
):
    """Offline fallback mode loads distinct Kharif drought trajectories per taluk."""
    poly = [
        [lon - 0.005, lat - 0.005],
        [lon + 0.005, lat - 0.005],
        [lon + 0.005, lat + 0.005],
        [lon - 0.005, lat + 0.005],
        [lon - 0.005, lat - 0.005],
    ]
    payload = {
        "farmer_name": "Siddappa",
        "crop_type": "Ragi",
        "taluk": taluk,
        "area_acres": 2.0,
        "polygon_coordinates": poly,
        "use_fallback": True,
    }
    with patch("backend.tts.synthesize_kannada_gtts", return_value="ZmFrZS1tcDM="):
        resp = await async_client.post("/api/analyze-plot", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["satellite"]["data_source"] == "fallback_cache"
    assert data["drought"]["stage"] == expected_stage

    ts = data["time_series"]
    assert len(ts["dates"]) == 10
    assert len(ts["baseline_ndvi"]) == 10
    assert len(ts["soil_moisture"]) == 10
    assert len(ts["et0"]) == 10
    if expect_onset:
        assert ts["stress_onset_date"] is not None
        assert ts["stress_onset_index"] is not None
    else:
        assert ts["stress_onset_date"] is None

    assert data["audio_base64"] == "ZmFrZS1tcDM="
    assert data["audio_mime"] == "audio/mpeg"
    assert data["audio_source"] == "gtts_kn"
    assert "ರಾಗಿ" in data["drought"]["recommendation_kn"]


# ── PDF Dossier Generation & SHA-256 / QR Verification ────────────────────────


def test_generate_pmfby_pdf_creates_valid_pdf_with_sha256(tmp_path: Path):
    """generate_pmfby_pdf produces a real PDF with embedded 64-char SHA-256 hash."""
    payload = {
        "plot_id": "test-plot-123",
        "farmer_name": "Ramaiah Gowda",
        "crop_type": "Ragi",
        "taluk": "Madhugiri",
        "area_acres": 2.5,
        "centroid_lat": 13.6621,
        "centroid_lon": 77.2017,
        "satellite": MOCK_SAT_DATA,
        "drought": {
            "stage": "severe_drought",
            "stage_label": "Severe Drought — File PMFBY Claim Now",
            "recommendation_en": "File PMFBY crop loss claim immediately.",
        },
        "hydromet": MOCK_HYDROMET_DATA,
        "time_series": {
            "dates": ["2026-06-15", "2026-08-15", "2026-10-30"],
            "stress_onset_date": "2026-08-15",
            "days_since_stress_onset": 76,
        },
    }
    pdf_path, sha256 = generate_pmfby_pdf(
        payload=payload,
        output_dir=str(tmp_path),
        verify_base_url="http://test",
    )
    pdf_file = Path(pdf_path)
    assert pdf_file.exists()
    content = pdf_file.read_bytes()
    assert content.startswith(b"%PDF")
    assert len(sha256) == 64
    assert all(c in "0123456789abcdef" for c in sha256)


@pytest.mark.anyio
async def test_dossier_endpoint_and_verify_roundtrip(
    async_client: AsyncClient, tmp_path: Path
):
    """Full end-to-end dossier generation, /api/plots/{id}/dossier, /api/verify, and PDF download."""
    with (
        patch("backend.main.settings.PDF_OUTPUT_DIR", str(tmp_path)),
        patch("backend.tts.synthesize_kannada_gtts", return_value=None),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)
        assert resp.status_code == 200, resp.text
        data = resp.json()

        plot_id = data["plot_id"]
        sha = data["pdf_sha256"]
        assert sha is not None and len(sha) == 64

        # Verify via /api/verify/{sha256}
        ver_resp = await async_client.get(f"/api/verify/{sha}")
        assert ver_resp.status_code == 200
        ver_data = ver_resp.json()
        assert ver_data["is_valid"] is True
        assert ver_data["plot_id"] == plot_id
        assert "time_series" in ver_data["claim_payload"]

        # Regional Office Monitor dossier generation endpoint
        dossier_resp = await async_client.post(f"/api/plots/{plot_id}/dossier")
        assert dossier_resp.status_code == 200, dossier_resp.text
        dossier = dossier_resp.json()
        assert dossier["sha256_hash"] == sha
        assert dossier["is_verified"] is True
        assert dossier["pdf_size_bytes"] > 0

        # Download generated PDF
        pdf_filename = dossier["pdf_download_url"].rsplit("/", 1)[-1]
        dl_resp = await async_client.get(f"/api/pdf/{pdf_filename}")
        assert dl_resp.status_code == 200
        assert dl_resp.headers["content-type"] == "application/pdf"
        assert dl_resp.content.startswith(b"%PDF")


# ── Kannada Advisory & gTTS Tests ────────────────────────────────────────────


def test_kannada_localized_crop_names_and_clean_sentences():
    """Kannada advisory uses localized crop names without raw English acronyms."""
    expected_crops = {
        "Ragi": "ರಾಗಿ",
        "Groundnut": "ಶೇಂಗಾ",
        "Maize": "ಮೆಕ್ಕೆಜೋಳ",
        "Pigeon Pea": "ತೊಗರಿ",
    }
    for en_crop, kn_crop in expected_crops.items():
        text = build_kannada_advisory_text(
            drought_stage="severe_drought",
            et0=5.8,
            survival_liters=234946.0,
            ndmi=-0.46,
            crop_type=en_crop,
        )
        assert kn_crop in text
        assert "NDMI" not in text
        assert "PMFBY" not in text
        assert text.count(".") >= 3


def test_gtts_kn_audio_success_and_offline_fallback():
    """gTTS returns spoken MP3 when online, and clean browser_tts mode when offline."""
    fake_tts = MagicMock()
    fake_tts.write_to_fp.side_effect = lambda buf: buf.write(b"ID3-fake-mp3")

    with patch("backend.tts.gTTS", return_value=fake_tts) as mock_gtts:
        audio_b64, mime, src, text_kn = generate_tts_advisory(
            farmer_name="Ramaiah",
            crop_type="Ragi",
            drought_stage="severe_drought",
            et0=5.8,
            survival_liters=234946.0,
            ndvi=0.09,
            ndmi=-0.46,
        )
    mock_gtts.assert_called_once()
    assert mock_gtts.call_args.kwargs["lang"] == "kn"
    assert base64.b64decode(audio_b64) == b"ID3-fake-mp3"
    assert mime == "audio/mpeg"
    assert src == "gtts_kn"
    assert "ರಾಗಿ" in text_kn

    # Offline / gTTS failure returns None (no dummy WAV beep) + browser_tts signal
    with patch("backend.tts.gTTS", side_effect=RuntimeError("offline")):
        audio_b64_off, mime_off, src_off, text_kn_off = generate_tts_advisory(
            farmer_name="Basavaraj",
            crop_type="Groundnut",
            drought_stage="moderate_drought",
            et0=5.4,
            survival_liters=197834.0,
            ndvi=0.18,
            ndmi=-0.31,
        )
    assert audio_b64_off is None
    assert mime_off == "text/plain"
    assert src_off == "browser_tts"
    assert "ಶೇಂಗಾ" in text_kn_off


# ── /api/verify/{sha256_hash} ─────────────────────────────────────────────────


@pytest.mark.anyio
async def test_verify_nonexistent_hash(async_client: AsyncClient):
    """A valid but non-existent hash should return is_valid=False."""
    fake_hash = "e" * 64
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
    """Database should return plots list with valid total."""
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
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/t.pdf", uuid.uuid4().hex * 2)),
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
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/t.pdf", uuid.uuid4().hex * 2)),
    ):
        resp = await async_client.post("/api/analyze-plot", json=VALID_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["drought"]["stage"] == "healthy"


# ── Regional Summary & Defaults Tests ─────────────────────────────────────────


@pytest.mark.anyio
async def test_officer_auth_gate_and_regional_summary(async_client: AsyncClient):
    """Protected endpoints require Officer Bearer token; login grants access."""
    # 1. Unauthenticated requests must be rejected with 401
    for protected_url in [
        "/api/regional/summary?taluk=ALL",
        "/api/history",
        "/api/photos/nonexistent.jpg",
    ]:
        unauth = await async_client.get(protected_url)
        assert unauth.status_code == 401, f"Expected 401 for {protected_url}"

    # 2. Invalid credentials rejected
    bad_login = await async_client.post(
        "/api/officer/login",
        json={"username": "officer@tumakuru.gov.in", "password": "wrong"},
    )
    assert bad_login.status_code == 401

    # 3. Valid officer login returns signed bearer token
    cfg = get_settings()
    login_resp = await async_client.post(
        "/api/officer/login",
        json={"username": cfg.OFFICER_USERNAME, "password": cfg.OFFICER_PASSWORD},
    )
    assert login_resp.status_code == 200, login_resp.text
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 4. Authorized regional summary & history work
    hist_resp = await async_client.get("/api/history", headers=headers)
    assert hist_resp.status_code == 200
    assert hist_resp.json()["total"] >= 8

    resp_all = await async_client.get("/api/regional/summary?taluk=ALL", headers=headers)
    assert resp_all.status_code == 200, resp_all.text
    data_all = resp_all.json()
    assert data_all["total_plots"] >= 8
    assert data_all["total_acres"] > 0
    assert data_all["severe_count"] >= 1
    assert data_all["moderate_count"] >= 1
    assert data_all["normal_count"] >= 1
    assert data_all["ready_for_audit_count"] >= 1
    assert len(data_all["plots"]) == data_all["total_plots"]

    first = data_all["plots"][0]
    for field in [
        "plot_id",
        "farmer_name",
        "district",
        "taluk",
        "crop_type",
        "area_acres",
        "drought_stage",
        "pmfby_eligible",
        "ndvi",
        "ndmi",
        "survival_liters",
        "created_at",
        "dossier_hash",
    ]:
        assert field in first

    resp_mad = await async_client.get(
        "/api/regional/summary?taluk=Madhugiri", headers=headers
    )
    assert resp_mad.status_code == 200
    mad_plots = resp_mad.json()["plots"]
    assert len(mad_plots) >= 1
    assert all(p["taluk"] == "Madhugiri" for p in mad_plots)

    resp_cn = await async_client.get(
        "/api/regional/summary?taluk=C.N. Halli", headers=headers
    )
    assert resp_cn.status_code == 200
    cn_plots = resp_cn.json()["plots"]
    assert len(cn_plots) >= 1
    assert all(p["taluk"] == "Chikkanayakanahalli" for p in cn_plots)


@pytest.mark.anyio
async def test_analyze_plot_defaults_farmer_and_infers_taluk(async_client: AsyncClient):
    """Omitting farmer_name and taluk defaults farmer_name and infers taluk from coords."""
    payload = {
        "crop_type": "Ragi",
        "area_acres": 1.5,
        "polygon_coordinates": VALID_POLYGON,
        "use_fallback": True,
    }
    with (
        patch("backend.main.fetch_sentinel2_indices", return_value=MOCK_SAT_DATA),
        patch("backend.main.get_hydromet_data", return_value=MOCK_HYDROMET_DATA),
        patch("backend.main.generate_voice_advisory", return_value=(None, "")),
        patch("backend.main.generate_pmfby_pdf", return_value=("/tmp/t.pdf", uuid.uuid4().hex * 2)),
    ):
        resp = await async_client.post("/api/analyze-plot", json=payload)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["farmer_name"] == "Tumakuru Farmer"
    assert data["taluk"] == "Madhugiri"


# ── Bhoomi / Dishaank Cadastral Lookup Tests ──────────────────────────────────


@pytest.mark.anyio
async def test_cadastral_villages_and_parcel(async_client: AsyncClient):
    """GET /api/cadastral/villages and /api/cadastral/parcel return valid Tumakuru parcels."""
    resp_all = await async_client.get("/api/cadastral/villages")
    assert resp_all.status_code == 200
    all_data = resp_all.json()
    assert len(all_data["villages"]) >= 9

    resp_mad = await async_client.get("/api/cadastral/villages?taluk=Madhugiri")
    assert resp_mad.status_code == 200
    mad_data = resp_mad.json()
    assert mad_data["taluk"] == "Madhugiri"
    assert len(mad_data["villages"]) >= 3
    assert all(v["taluk"] == "Madhugiri" for v in mad_data["villages"])

    resp_cn = await async_client.get("/api/cadastral/villages?taluk=C.N. Halli")
    assert resp_cn.status_code == 200
    assert resp_cn.json()["taluk"] == "Chikkanayakanahalli"

    resp_parcel = await async_client.get(
        "/api/cadastral/parcel?taluk=Madhugiri&village=Kodigenahalli&survey_no=42/1"
    )
    assert resp_parcel.status_code == 200, resp_parcel.text
    parcel = resp_parcel.json()
    assert parcel["taluk"] == "Madhugiri"
    assert parcel["hobli"] == "Kasaba"
    assert parcel["village"] == "Kodigenahalli"
    assert parcel["survey_no"] == "42/1"
    assert parcel["acres"] > 0
    assert parcel["soil_type"]
    assert parcel["default_crop"]
    assert len(parcel["coordinates"]) >= 4
    assert parcel["geojson"]["geometry"]["type"] == "Polygon"

    resp_missing = await async_client.get(
        "/api/cadastral/parcel?taluk=Madhugiri&village=Kodigenahalli&survey_no=999/9"
    )
    assert resp_missing.status_code == 404

    # Expanded multi-district coverage check
    taluks_present = {v["taluk"] for v in all_data["villages"]}
    for expected_taluk in [
        "Madhugiri",
        "Koratagere",
        "Chikkanayakanahalli",
        "Pavagada",
        "Sira",
        "Challakere",
        "Hiriyur",
        "Bagepalli",
        "Kalaburagi",
        "Vijayapura",
    ]:
        assert expected_taluk in taluks_present, f"Missing taluk: {expected_taluk}"

    challakere = await async_client.get(
        "/api/cadastral/parcel?taluk=Challakere&village=Nayakanahatti&survey_no=88/1"
    )
    assert challakere.status_code == 200
    assert challakere.json()["district"] == "Chitradurga"


@pytest.mark.anyio
async def test_geotagged_photo_upload_and_pdf_embedding(
    async_client: AsyncClient, tmp_path: Path
):
    """Geotagged photo upload saves image, computes photo_sha256, folds into PDF & protects photo route."""
    buf = io.BytesIO()
    PILImage.new("RGB", (64, 48), color=(180, 90, 40)).save(buf, format="PNG")
    png_bytes = buf.getvalue()
    expected_photo_sha = hashlib.sha256(png_bytes).hexdigest()
    photo_b64 = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    severe_sat = {**MOCK_SAT_DATA, "ndvi": 0.08, "ndmi": -0.48}
    payload = {
        **VALID_PAYLOAD,
        "phone_number": "+91 98451 99999",
        "irrigation_source": "Purely Rain-Fed",
        "observed_symptoms": ["Soil Cracking", "Leaf Wilting"],
        "photo_base64": photo_b64,
        "photo_filename": "field.png",
        "photo_lat": 13.6621,
        "photo_lon": 77.2017,
        "photo_timestamp": "2026-10-30T09:15:00Z",
    }
    pdf_dir = tmp_path / "pdfs"
    photo_dir = tmp_path / "photos"
    with (
        patch("backend.main.settings.PDF_OUTPUT_DIR", str(pdf_dir)),
        patch("backend.main.settings.PHOTO_UPLOAD_DIR", str(photo_dir)),
        patch("backend.main.fetch_sentinel2_indices", return_value=severe_sat),
        patch("backend.main.get_hydromet_data", return_value=MOCK_HYDROMET_DATA),
        patch("backend.main.generate_voice_advisory", return_value=(None, "")),
    ):
        resp = await async_client.post("/api/analyse", json=payload)

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["photo_sha256"] == expected_photo_sha
        assert data["pmfby_eligible"] == "ELIGIBLE — Severe Moisture Deficit"
        assert data["irrigation_source"] == "Purely Rain-Fed"
        assert data["observed_symptoms"] == ["Soil Cracking", "Leaf Wilting"]
        assert data["pdf_sha256"] and len(data["pdf_sha256"]) == 64

        # Verify photo SHA-256 is folded into stored claim_payload
        ver_resp = await async_client.get(f"/api/verify/{data['pdf_sha256']}")
        assert ver_resp.status_code == 200
        ver_data = ver_resp.json()
        assert ver_data["is_valid"] is True
        assert ver_data["claim_payload"]["photo_sha256"] == expected_photo_sha

        # Photo route is protected without token, accessible with officer token
        photo_filename = data["photo_url"].rsplit("/", 1)[-1]
        unauth_photo = await async_client.get(f"/api/photos/{photo_filename}")
        assert unauth_photo.status_code == 401

        cfg = get_settings()
        login_resp = await async_client.post(
            "/api/officer/login",
            json={"username": cfg.OFFICER_USERNAME, "password": cfg.OFFICER_PASSWORD},
        )
        token = login_resp.json()["access_token"]
        auth_photo = await async_client.get(
            f"/api/photos/{photo_filename}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert auth_photo.status_code == 200
        assert auth_photo.content == png_bytes


@pytest.mark.anyio
async def test_analyze_plot_with_cadastral_metadata(
    async_client: AsyncClient, tmp_path: Path
):
    """Survey number, village, and hobli persist and appear in analyze response & PDF."""
    parcel_resp = await async_client.get(
        "/api/cadastral/parcel?taluk=Koratagere&village=Kolala&survey_no=31/1"
    )
    parcel = parcel_resp.json()
    payload = {
        "farmer_name": "Nanjundappa",
        "crop_type": parcel["default_crop"],
        "taluk": parcel["taluk"],
        "hobli": parcel["hobli"],
        "village": parcel["village"],
        "survey_no": parcel["survey_no"],
        "area_acres": parcel["acres"],
        "polygon_coordinates": parcel["coordinates"],
        "use_fallback": True,
    }
    with (
        patch("backend.main.settings.PDF_OUTPUT_DIR", str(tmp_path)),
        patch("backend.main.fetch_sentinel2_indices", return_value=MOCK_SAT_DATA),
        patch("backend.main.get_hydromet_data", return_value=MOCK_HYDROMET_DATA),
        patch("backend.main.generate_voice_advisory", return_value=(None, "")),
    ):
        resp = await async_client.post("/api/analyze-plot", json=payload)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["village"] == "Kolala"
    assert data["hobli"] == "Kasaba"
    assert data["survey_no"] == "31/1"
    assert data["pdf_sha256"] and len(data["pdf_sha256"]) == 64
