"""
SookshmaJal – Configuration
Loads all secrets and settings from .env via Pydantic BaseSettings.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "sqlite+aiosqlite:///./sookshmajal.db"

    # ── Sarvam AI ─────────────────────────────────────────────────────────────
    SARVAM_API_KEY: str = ""
    SARVAM_TTS_MODEL: str = "bulbul:v1"
    SARVAM_TRANSLATE_MODEL: str = "sarvam-translate:v1"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    # ── Planetary Computer ────────────────────────────────────────────────────
    PLANETARY_COMPUTER_API_KEY: str = ""

    # ── App ───────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    PDF_OUTPUT_DIR: str = "generated_pdfs"
    PHOTO_UPLOAD_DIR: str = "uploaded_photos"
    FALLBACK_CACHE_DIR: str = "fallback_cache"

    # ── Officer Auth ──────────────────────────────────────────────────────────
    OFFICER_USERNAME: str = "officer@tumakuru.gov.in"
    OFFICER_PASSWORD: str = "VECTORZZ2026"
    OFFICER_SECRET_KEY: str = "sookshmajal-hackwarts-secret"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_ANALYZE: str = "10/minute"
    RATE_LIMIT_VERIFY: str = "30/minute"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
