# SookshmaJal

> **Zero-hardware, plot-level Sentinel-2 satellite moisture & FAO-56 ET₀ decision engine for drought survival and SHA-256 PMFBY crop-loss ground-truthing in Tumakuru, Karnataka.**

---

## Team VECTORZZ — Hackwarts 2026 AgriTech Track

| Member | Role |
|--------|------|
| **Akshay** | Backend · Satellite & Hydromet Engine |
| **Ritesh** | Frontend · UI/UX & Leaflet Integration |
| **Sunil**  | ML / NDVI-Drought Classification & PDF Gen |
| **Rohith** | DevOps · Docker · CI/CD · API Security |

---

## Architecture Overview

```
                     ┌─────────────────────────────────────────────┐
                     │          SookshmaJal (FastAPI 0.115.6)       │
                     │                port 8000                     │
                     └─────────────┬────────────────┬──────────────┘
                                   │                │
              ┌────────────────────▼──┐    ┌────────▼──────────────────┐
              │  Planetary Computer    │    │  Open-Meteo API (free)    │
              │  STAC sentinel-2-l2a   │    │  FAO-56 ET₀ · Precip      │
              │  (B04,B05,B08,B11,SCL) │    │  Soil Moisture 0-7cm      │
              └────────────────────┬──┘    └────────┬──────────────────┘
                                   │                │
                        ┌──────────▼────────────────▼──────┐
                        │  Analysis Pipeline               │
                        │  NDVI · NDMI · NDRE              │
                        │  Drought Stage Classification    │
                        │  V_surv survival litres          │
                        └──────────┬───────────────────────┘
                                   │
              ┌────────────────────┼────────────────────────┐
              │                    │                        │
   ┌──────────▼──────┐   ┌────────▼──────────┐   ┌────────▼────────────┐
   │  Sarvam AI       │   │  ReportLab PDF     │   │  SQLAlchemy DB      │
   │  Kannada TTS     │   │  PMFBY Dossier     │   │  FarmPlot           │
   │  bulbul:v1       │   │  SHA-256 + QR      │   │  TelemetryLog       │
   │  (+ fallback)    │   │  (tamper-evident)  │   │  ClaimDossier       │
   └──────────────────┘   └────────────────────┘   └─────────────────────┘
```

### Key Features

| Feature | Implementation |
|---------|---------------|
| 🛰 **Satellite moisture** | Sentinel-2 L2A via Planetary Computer STAC · COG windowed reads |
| 💧 **NDVI / NDMI / NDRE** | Band math on B04, B05, B08, B11 with SCL cloud masking |
| ☀️ **FAO-56 ET₀** | Penman-Monteith implementation with Open-Meteo 7-day data |
| 🌊 **V_surv** | Minimum survival litres formula with crop Kc and irrigation efficiency |
| 🔊 **Kannada advisory** | Sarvam AI `bulbul:v1` TTS + `sarvam-translate:v1` with offline fallback |
| 📄 **PMFBY PDF** | ReportLab dossier with embedded SHA-256 hash + QR verification code |
| ✅ **Tamper-evidence** | `GET /api/verify/{sha256_hash}` — cryptographic anchoring |
| 📱 **Zero-hardware** | No sensors — pure satellite + open weather data |
| 🌐 **Offline resilience** | Pre-cached JSON payloads for 3 Tumakuru taluks |

---

## Directory Structure

```
sookshmajal-hackwarts2026/
├── .github/workflows/ci.yml     # Ruff lint + pytest on push/PR
├── backend/
│   ├── config.py                # Pydantic BaseSettings (.env)
│   ├── database.py              # Async SQLAlchemy (SQLite/PostgreSQL)
│   ├── models.py                # FarmPlot, TelemetryLog, ClaimDossier
│   ├── schemas.py               # Request/response validators + KA geofence
│   ├── satellite.py             # Planetary Computer STAC → NDVI/NDMI/NDRE
│   ├── hydromet.py              # Open-Meteo → FAO-56 ET₀ + V_surv
│   ├── voice.py                 # Sarvam AI Kannada TTS + fallback
│   ├── pdf_gen.py               # ReportLab PMFBY dossier + SHA-256 + QR
│   ├── main.py                  # FastAPI app + all routes
│   └── requirements.txt
├── frontend/
│   ├── tokens.css               # Design tokens (Apple IN, DESIGN.md)
│   ├── styles.css               # Apple-inspired UI, all interactive states
│   ├── index.html               # Map, presets, telemetry cards, audio, modal
│   └── app.js                   # Leaflet + Chart.js + API client + audio
├── fallback_cache/
│   ├── madhugiri_sample.json
│   ├── koratagere_sample.json
│   └── cnhalli_sample.json
├── tests/
│   ├── test_hydromet.py
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- `libgdal-dev` (Linux) or GDAL via Homebrew (macOS)
- Docker + Docker Compose (optional)

### Local Development

```bash
# 1. Clone
git clone <repo-url>
cd sookshmajal-hackwarts2026

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r backend/requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — add SARVAM_API_KEY if available (optional)

# 5. Run the server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 6. Open browser
# http://localhost:8000
# API docs: http://localhost:8000/api/docs
```

### Docker (Recommended for Hackathon Demo)

```bash
# Build and run
docker-compose up --build

# Or in detached mode
docker-compose up -d --build

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

### Run Tests

```bash
pip install pytest==8.3.4 pytest-anyio anyio httpx
python -m pytest tests/ -v --asyncio-mode=auto
```

### Run Linter

```bash
pip install ruff==0.8.4
ruff check backend/ tests/ --select=E,W,F,I,B,UP
```

---

## API Reference

### `GET /health`
Liveness probe.
```json
{
  "status": "ok",
  "version": "1.0.0",
  "team": "VECTORZZ",
  "hackathon": "Hackwarts 2026",
  "timestamp": "2026-11-25T10:00:00+00:00"
}
```

### `POST /api/analyze-plot`
Full satellite + hydromet analysis.

**Request body:**
```json
{
  "farmer_name": "Ramaiah Gowda",
  "crop_type": "Ragi",
  "taluk": "Madhugiri",
  "area_acres": 2.5,
  "polygon_coordinates": [[77.19, 13.66], [77.20, 13.66], [77.20, 13.67], [77.19, 13.67], [77.19, 13.66]]
}
```

**Validation rules:**
- `area_acres`: 0.1 – 50
- `polygon_coordinates`: Karnataka lat/lon geofence, minimum 4 vertices

**Response:** Full `AnalyzePlotResponse` including NDVI, NDMI, NDRE, ET₀, survival litres, drought stage, Kannada advisory, PDF SHA-256 hash.

### `GET /api/verify/{sha256_hash}`
Verify a PMFBY dossier by its 64-character SHA-256 hex hash.

### `GET /api/plots`
List all analysed plots (last 100).

### `GET /api/pdf/{filename}`
Download a generated PMFBY PDF.

---

## Design System

The frontend strictly follows the **Apple (IN) design system** extracted from `SKILL.md` / `DESIGN.md`:

| Token | Value | Usage |
|-------|-------|-------|
| `color-1` | `#1D1D1F` | Primary text |
| `color-2` | `#0066CC` | Accent / healthy / CTA |
| `color-3` | `#B64400` | Critical / severe drought |
| `color-4` | `#6E6E73` | Secondary text |
| `color-5` | `#FF791B` | Warning / early stress |
| `color-7` | `#E8E8ED` | Surface background |
| `color-8` | `#FFFFFF` | Card light |

Typography: `-apple-system, BlinkMacSystemFont` · weights 400 & 600 only  
Spacing: 4px grid  
Border radii: `28px`, `36px`, `50%`, `980px` (pills)  
One primary CTA per viewport. WCAG 2.2 AA contrast.

---

## Drought Classification Logic

| NDVI | NDMI | Stage | Color Token |
|------|------|-------|-------------|
| ≥ 0.35 | ≥ 0.0 | `healthy` | `color-2` (#0066CC) |
| ≥ 0.2 | ≥ −0.2 | `early_stress` | `color-5` (#FF791B) |
| ≥ 0.1 | ≥ −0.4 | `moderate_drought` | `color-5` (#FF791B) |
| < 0.1 | < −0.4 | `severe_drought` | `color-3` (#B64400) |

---

## FAO-56 ET₀ Formula

$$ET_0 = \frac{0.408 \Delta (R_n - G) + \gamma \frac{900}{T + 273} u_2 (e_s - e_a)}{\Delta + \gamma (1 + 0.34 u_2)}$$

Where Δ = slope of SVP curve, γ = psychrometric constant (adjusted for Tumakuru elevation ~820 m MSL), u₂ = wind speed at 2 m height.

**Survival litres:**
$$V_{surv} = \max\!\left(0,\ \frac{K_c \cdot ET_0 \cdot days - P}{\eta} \times A_{m^2}\right) \times 1000\ \text{L/m}^3$$

---

## Offline Hackathon Resilience

If Planetary Computer and Open-Meteo are unreachable (poor venue Wi-Fi), the system automatically loads pre-cached JSON payloads from `fallback_cache/`:

| Taluk | Cache File | Drought Stage |
|-------|-----------|---------------|
| Madhugiri | `madhugiri_sample.json` | Early Stress |
| Koratagere | `koratagere_sample.json` | Moderate Drought |
| Chikkanayakanahalli | `cnhalli_sample.json` | Severe Drought |

---

## Security

- **Rate limiting:** 10 req/min on `/api/analyze-plot` via `slowapi`
- **Geofence validation:** All polygon coordinates checked against Karnataka bounding box (11.5–18.5°N, 74–78.5°E)
- **Input sanitisation:** Strict Pydantic validators on all fields
- **Path traversal prevention:** PDF download route sanitises filenames
- **Secrets:** Never hardcoded — loaded from `.env` via `python-dotenv`
- **CORS allowlist:** Configurable via `ALLOWED_ORIGINS`

---

## License

MIT License — Hackwarts 2026 · Team VECTORZZ

---

*Built with ❤️ for Indian farmers by Team VECTORZZ — Akshay, Ritesh, Sunil, Rohith*
