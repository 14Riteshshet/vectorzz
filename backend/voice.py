"""
SookshmaJal – Sarvam AI Kannada TTS advisory generator.
Uses Sarvam AI bulbul:v1 for Kannada speech synthesis and
sarvam-translate:v1 for English→Kannada translation.
Automatically falls back to a synthesized playable WAV audio asset and
pre-translated Kannada guidance text when SARVAM_API_KEY is missing or times out.
"""

from __future__ import annotations

import base64
import io
import logging
import math
import struct
import wave

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


def synthesize_fallback_wav(drought_stage: str = "early_stress") -> str:
    """
    Synthesize a valid, playable 22050 Hz 16-bit mono PCM WAV audio chime
    corresponding to the drought severity stage, encoded as base64.
    Never raises on error.
    """
    sample_rate = 22050
    tone_patterns: dict[str, list[tuple[float, float]]] = {
        "healthy": [(523.25, 0.22), (659.25, 0.22), (783.99, 0.32)],
        "early_stress": [(440.0, 0.25), (392.0, 0.35)],
        "moderate_drought": [(587.33, 0.22), (440.0, 0.22), (587.33, 0.30)],
        "severe_drought": [
            (783.99, 0.18),
            (659.25, 0.18),
            (783.99, 0.18),
            (659.25, 0.30),
        ],
    }
    notes = tone_patterns.get(drought_stage, tone_patterns["early_stress"])
    gap_samples = int(0.06 * sample_rate)

    frames = bytearray()
    for freq, dur in notes:
        n_samples = int(dur * sample_rate)
        fade_len = max(1, int(0.02 * sample_rate))
        for i in range(n_samples):
            env = 1.0
            if i < fade_len:
                env = i / fade_len
            elif i > n_samples - fade_len:
                env = (n_samples - i) / fade_len
            sample = int(
                11000 * env * math.sin(2.0 * math.pi * freq * (i / sample_rate))
            )
            frames.extend(struct.pack("<h", sample))
        frames.extend(b"\x00\x00" * gap_samples)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(bytes(frames))

    return base64.b64encode(buf.getvalue()).decode("ascii")


def translate_to_kannada(text_en: str) -> str | None:
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


def synthesize_kannada_tts(text_kn: str) -> str | None:
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


def build_kannada_advisory_text(
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndmi: float,
    crop_type: str = "",
) -> str:
    """
    Return a pre-translated, stage-specific Kannada advisory string for offline fallback.
    """
    crop_prefix = f"{crop_type} ಬೆಳೆಗೆ " if crop_type else "ನಿಮ್ಮ ಬೆಳೆಗೆ "
    daily_l = survival_liters / 7.0

    if drought_stage == "healthy":
        return (
            f"{crop_prefix}ತೇವಾಂಶ ಸಮರ್ಪಕವಾಗಿದೆ (NDMI {ndmi:.2f}). "
            f"ದೈನಿಕ ನೀರಿನ ಅವಶ್ಯಕತೆ {et0:.1f} ಮಿ.ಮೀ (ಸುಮಾರು {daily_l:,.0f} ಲೀಟರ್/ದಿನ). "
            "ಬೋರ್‌ವೆಲ್ ಅತಿಯಾದ ಪಂಪಿಂಗ್ ತಪ್ಪಿಸಿ, ಹೂಬಿಡುವ ಹಂತದಲ್ಲಿ ನಿಯಮಿತ ನೀರಾವರಿ ಮುಂದುವರಿಸಿ."
        )
    elif drought_stage == "early_stress":
        return (
            f"{crop_prefix}ಆರಂಭಿಕ ತೇವಾಂಶ ಒತ್ತಡ ಪತ್ತೆಯಾಗಿದೆ (NDMI {ndmi:.2f}). "
            f"ಮುಂದಿನ 7 ದಿನಗಳಿಗೆ ಕನಿಷ್ಠ {survival_liters:,.0f} ಲೀಟರ್ (ದಿನಕ್ಕೆ {daily_l:,.0f} ಲೀ) ಜೀವ ರಕ್ಷಕ ನೀರು ಅಗತ್ಯ. "
            "ಹೊದಿಕೆ (ಮಲ್ಚ್) ಹಾಕಿ, ಹನಿ ನೀರಾವರಿ ಮೂಲಕ ಬೇರಿಗೆ ಮಾತ್ರ ನೀರು ನೀಡಿ."
        )
    elif drought_stage == "moderate_drought":
        return (
            f"{crop_prefix}ಮಧ್ಯಮ ಬರ ಒತ್ತಡದಲ್ಲಿದೆ (NDMI {ndmi:.2f}). "
            f"ತಕ್ಷಣ 7 ದಿನಗಳಲ್ಲಿ {survival_liters:,.0f} ಲೀಟರ್ (ದಿನಕ್ಕೆ {daily_l:,.0f} ಲೀ) ಮಿತ ನೀರಾವರಿ ನೀಡಿ. "
            "ಹೂಬಿಡುವ/ಕಾಳು ಕಟ್ಟುವ ಹಂತವನ್ನು ಉಳಿಸಲು ತಾಲ್ಲೂಕು ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ ಮತ್ತು PMFBY ದಾಖಲಾತಿ ಆರಂಭಿಸಿ."
        )
    else:
        return (
            f"ತುರ್ತು ಎಚ್ಚರಿಕೆ: {crop_prefix}ತೀವ್ರ ಬರ ಒತ್ತಡ ಪತ್ತೆಯಾಗಿದೆ (NDMI {ndmi:.2f}). "
            f"ಬೆಳೆ ಉಳಿಸಲು {survival_liters:,.0f} ಲೀಟರ್ ತುರ್ತು ನೀರು ಅಗತ್ಯ; ಬೋರ್‌ವೆಲ್ ಖಾಲಿ ಮಾಡದೆ ಬೇರಿಗೆ ನೀರು ಹಾಯಿಸಿ. "
            "ಈಗಲೇ PMFBY ಬೆಳೆ ನಷ್ಟ ದಾವೆ ಸಲ್ಲಿಸಿ ಮತ್ತು ಹೊಲದ ಛಾಯಾಚಿತ್ರ ಸಂಗ್ರಹಿಸಿ."
        )


def generate_voice_advisory(
    farmer_name: str,
    crop_type: str,
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndvi: float,
    ndmi: float,
) -> tuple[str | None, str]:
    """
    Generate Kannada voice advisory.
    Returns (audio_base64, advisory_text_kn).
    Never raises — gracefully falls back to synthesized WAV + Kannada text when
    SARVAM_API_KEY is missing, times out, or fails.
    """
    text_en = _build_advisory_english(
        farmer_name, crop_type, drought_stage, et0, survival_liters, ndvi, ndmi
    )
    fallback_kn = build_kannada_advisory_text(
        drought_stage=drought_stage,
        et0=et0,
        survival_liters=survival_liters,
        ndmi=ndmi,
        crop_type=crop_type,
    )

    try:
        # Try full Sarvam pipeline
        text_kn = translate_to_kannada(text_en)
        if text_kn:
            audio_b64 = synthesize_kannada_tts(text_kn)
            if audio_b64:
                logger.info("Sarvam TTS pipeline succeeded for farmer %s.", farmer_name)
                return audio_b64, text_kn
    except Exception as exc:
        logger.warning("Sarvam voice pipeline exception (%s); using WAV fallback.", exc)

    # Graceful offline / timeout fallback: playable WAV asset + Kannada advisory text
    logger.info(
        "Using synthesized WAV + Kannada text fallback for farmer %s.", farmer_name
    )
    try:
        fallback_wav = synthesize_fallback_wav(drought_stage)
    except Exception as exc:
        logger.error("Fallback WAV synthesis error: %s", exc)
        fallback_wav = None
    return fallback_wav, fallback_kn
