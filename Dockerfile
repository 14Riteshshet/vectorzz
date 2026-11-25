# ── SookshmaJal Dockerfile ──────────────────────────────────────────────────
# Production container – python:3.11-slim + GDAL/rasterio system libs
# Team VECTORZZ · Hackwarts 2026

FROM python:3.11-slim AS base

# ── System packages: GDAL + rasterio prerequisites ──────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    gdal-bin \
    build-essential \
    curl \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Python env ───────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ── Install Python deps (cached layer) ──────────────────────────────────────
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --upgrade pip && \
    pip install -r backend/requirements.txt

# ── Copy application code ────────────────────────────────────────────────────
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY fallback_cache/ ./fallback_cache/
COPY .env.example .env.example

# ── Create runtime dirs ───────────────────────────────────────────────────────
RUN mkdir -p generated_pdfs

# ── Non-root user for security ───────────────────────────────────────────────
RUN groupadd -r sookshmajal && useradd -r -g sookshmajal sookshmajal && \
    chown -R sookshmajal:sookshmajal /app
USER sookshmajal

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ── Expose & run ─────────────────────────────────────────────────────────────
EXPOSE 8000

CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--loop", "uvloop", \
     "--log-level", "info"]
