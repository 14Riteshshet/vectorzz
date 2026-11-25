"""
SookshmaJal – Sarvam AI Kannada TTS advisory generator.
Uses Sarvam AI bulbul:v1 for Kannada speech synthesis and
sarvam-translate:v1 for English→Kannada translation.
Automatically falls back to English text advisory when API unavailable.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

import requests

from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"


def _build_advisory_english(
    farmer_name: str,
    crop_type: str,
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndvi: float,
    ndmi: float,
) -> str:
    """Build English advisory text based on drought stage."""
    base = f"Dear {farmer_name}, analysis of your {crop_type} plot is complete. "

    if drought_stage == "healthy":
        advice = (
            f"Your crop is healthy. NDVI is {ndvi:.2f} and soil moisture index NDMI is {ndmi:.2f}. "
            f"Daily water requirement is approximately {et0:.1f} millimeters. "
            "Continue regular irrigation. No immediate action needed."
        )
    elif drought_stage == "early_stress":
        advice = (
            f"Early moisture stress detected. NDVI is {ndvi:.2f}, NDMI is {ndmi:.2f}. "
            f"Your crop needs at least {survival_liters:.0f} liters over the next 7 days. "
            "Increase irrigation frequency. Apply mulch to reduce evaporation."
        )
    elif drought_stage == "moderate_drought":
        advice = (
            f"Moderate drought stress. NDVI is {ndvi:.2f}, NDMI is {ndmi:.2f}. "
            f"Urgently irrigate with {survival_liters:.0f} liters over 7 days. "
            "Consider deficit irrigation strategy. Contact your taluk agricultural officer."
        )
    else:  # severe_drought
        advice = (
            f"ALERT: Severe drought detected. NDVI is {ndvi:.2f}, NDMI is {ndmi:.2f}. "
            f"Immediate irrigation of {survival_liters:.0f} liters required to prevent crop loss. "
            "File PMFBY crop loss claim immediately. Document field conditions with photographs."
        )

    return base + advice


def translate_to_kannada(text_en: str) -> Optional[str]:
    """Translate English advisory to Kannada via Sarvam AI."""
    if not settings.SARVAM_API_KEY:
        return None
    try:
        resp = requests.post(
            SARVAM_TRANSLATE_URL,
            json={
                "input": text_en,
                "source_language_code": "en-IN",
                "target_language_code": "kn-IN",
                "speaker_gender": "Male",
                "mode": "formal",
                "model": settings.SARVAM_TRANSLATE_MODEL,
                "enable_preprocessing": True,
            },
            headers={
                "api-subscription-key": settings.SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("translated_text", text_en)
    except Exception as exc:
        logger.warning("Sarvam translate failed: %s", exc)
        return None


def synthesize_kannada_tts(text_kn: str) -> Optional[str]:
    """
    Synthesize Kannada audio via Sarvam bulbul:v1.
    Returns base64-encoded WAV string or None on failure.
    """
    if not settings.SARVAM_API_KEY:
        return None
    try:
        resp = requests.post(
            SARVAM_TTS_URL,
            json={
                "inputs": [text_kn],
                "target_language_code": "kn-IN",
                "speaker": "meera",
                "pitch": 0,
                "pace": 1.0,
                "loudness": 1.5,
                "speech_sample_rate": 22050,
                "enable_preprocessing": True,
                "model": settings.SARVAM_TTS_MODEL,
            },
            headers={
                "api-subscription-key": settings.SARVAM_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        audios = resp.json().get("audios", [])
        if audios:
            return audios[0]  # Already base64 string from Sarvam
        return None
    except Exception as exc:
        logger.warning("Sarvam TTS failed: %s", exc)
        return None


def generate_voice_advisory(
    farmer_name: str,
    crop_type: str,
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndvi: float,
    ndmi: float,
) -> tuple[Optional[str], str]:
    """
    Generate Kannada voice advisory.
    Returns (audio_base64_or_None, advisory_text_kn_or_en).
    """
    text_en = _build_advisory_english(
        farmer_name, crop_type, drought_stage, et0, survival_liters, ndvi, ndmi
    )

    # Try full Sarvam pipeline
    text_kn = translate_to_kannada(text_en)
    if text_kn:
        audio_b64 = synthesize_kannada_tts(text_kn)
        if audio_b64:
            logger.info("Sarvam TTS pipeline succeeded for farmer %s.", farmer_name)
            return audio_b64, text_kn

    # Fallback: return English text, no audio
    logger.info("Using fallback text advisory for farmer %s.", farmer_name)
    return None, text_en


def build_kannada_advisory_text(
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndmi: float,
) -> str:
    """
    Return a minimal pre-translated Kannada advisory string for offline fallback.
    These are real Kannada translations of the core messages.
    """
    if drought_stage == "healthy":
        return (
            f"ನಿಮ್ಮ ಬೆಳೆ ಆರೋಗ್ಯಕರವಾಗಿದೆ. ದೈನಿಕ ನೀರಿನ ಅವಶ್ಯಕತೆ {et0:.1f} ಮಿ.ಮೀ. "
            "ನಿಯಮಿತ ನೀರಾವರಿ ಮುಂದುವರಿಸಿ."
        )
    elif drought_stage == "early_stress":
        return (
            f"ಆರಂಭಿಕ ತೇವಾಂಶ ಒತ್ತಡ ಪತ್ತೆಯಾಗಿದೆ. 7 ದಿನಗಳಲ್ಲಿ {survival_liters:.0f} ಲೀಟರ್ ನೀರು ಬೇಕು. "
            "ನೀರಾವರಿ ಹೆಚ್ಚಿಸಿ."
        )
    elif drought_stage == "moderate_drought":
        return (
            f"ಮಧ್ಯಮ ಬರ ಒತ್ತಡ. {survival_liters:.0f} ಲೀಟರ್ ನೀರು ತಕ್ಷಣ ನೀಡಿ. "
            "ತಾಲ್ಲೂಕು ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ."
        )
    else:
        return (
            f"ಎಚ್ಚರಿಕೆ: ತೀವ್ರ ಬರ. {survival_liters:.0f} ಲೀಟರ್ ನೀರು ತಕ್ಷಣ ಅಗತ್ಯ. "
            "PMFBY ಬೆಳೆ ನಷ್ಟ ದಾವೆ ಸಲ್ಲಿಸಿ."
        )
