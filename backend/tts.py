"""
SookshmaJal – Kannada Advisory & Spoken TTS Generator.
Builds natural, localized Kannada farmer guidance with short sentences
and clear pauses, and synthesizes real spoken Kannada MP3 audio via gTTS
when online (or cleanly signals browser speechSynthesis when offline).
"""

from __future__ import annotations

import base64
import io
import logging

try:
    from gtts import gTTS

    _GTTS_AVAILABLE = True
except ImportError:
    _GTTS_AVAILABLE = False

logger = logging.getLogger(__name__)

_CROP_KN: dict[str, str] = {
    "ragi": "ರಾಗಿ",
    "groundnut": "ಶೇಂಗಾ",
    "maize": "ಮೆಕ್ಕೆಜೋಳ",
    "pigeon pea": "ತೊಗರಿ",
    "togari": "ತೊಗರಿ",
    "tur": "ತೊಗರಿ",
    "tomato": "ಟೊಮೇಟೊ",
    "sunflower": "ಸೂರ್ಯಕಾಂತಿ",
    "sorghum": "ಜೋಳ",
    "cotton": "ಹತ್ತಿ",
    "rice": "ಭತ್ತ",
}


def localize_crop_kn(crop_type: str) -> str:
    """Return localized Kannada crop name, defaulting to a clean fallback."""
    key = (crop_type or "").strip().lower()
    if key in _CROP_KN:
        return _CROP_KN[key]
    return crop_type.strip() if crop_type and crop_type.strip() else "ನಿಮ್ಮ"


def build_kannada_advisory_text(
    drought_stage: str,
    et0: float = 0.0,
    survival_liters: float = 0.0,
    ndmi: float = 0.0,
    crop_type: str = "",
) -> str:
    """
    Build short, natural Kannada sentences with localized crop names and clear
    pauses, keeping raw technical numbers out of the spoken sentence body.
    """
    crop_kn = localize_crop_kn(crop_type)
    daily_l = max(0, round(survival_liters / 7.0))
    daily_txt = f"{daily_l:,}"

    if drought_stage == "healthy":
        return (
            f"{crop_kn} ಬೆಳೆ ಆರೋಗ್ಯಕರವಾಗಿದೆ. "
            "ಮಣ್ಣಿನಲ್ಲಿ ತೇವಾಂಶ ಚೆನ್ನಾಗಿದೆ. "
            f"ದಿನಕ್ಕೆ ಸುಮಾರು {daily_txt} ಲೀಟರ್ ನೀರು ಸಾಕು. "
            "ಹೂಬಿಡುವ ಹಂತದಲ್ಲಿ ನಿಯಮಿತ ನೀರಾವರಿ ಮುಂದುವರಿಸಿ."
        )
    if drought_stage == "early_stress":
        return (
            f"{crop_kn} ಬೆಳೆಯಲ್ಲಿ ಆರಂಭಿಕ ನೀರಿನ ಕೊರತೆ ಕಂಡುಬಂದಿದೆ. "
            f"ಮುಂದಿನ ಏಳು ದಿನಗಳಿಗೆ ದಿನಕ್ಕೆ {daily_txt} ಲೀಟರ್ ನೀರು ಕೊಡಿ. "
            "ಮಣ್ಣಿನ ತೇವಾಂಶ ಉಳಿಸಲು ಹೊದಿಕೆ ಹಾಕಿ. "
            "ಬೋರ್‌ವೆಲ್ ನೀರನ್ನು ಮಿತವಾಗಿ ಬಳಸಿ."
        )
    if drought_stage == "moderate_drought":
        return (
            f"{crop_kn} ಬೆಳೆಗೆ ಮಧ್ಯಮ ಬರ ಒತ್ತಡ ತಗುಲಿದೆ. "
            f"ತಕ್ಷಣ ದಿನಕ್ಕೆ {daily_txt} ಲೀಟರ್ ಜೀವ ರಕ್ಷಕ ನೀರು ಹಾಯಿಸಿ. "
            "ಬೋರ್‌ವೆಲ್ ಖಾಲಿಯಾಗದಂತೆ ಬೇರಿಗೆ ಮಾತ್ರ ನೀರು ಕೊಡಿ. "
            "ಕೃಷಿ ಅಧಿಕಾರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ ಬೆಳೆ ವಿಮೆ ದಾಖಲೆ ಸಿದ್ಧಪಡಿಸಿ."
        )
    return (
        f"{crop_kn} ಬೆಳೆಯಲ್ಲಿ ತೀವ್ರ ಬರ ಪರಿಸ್ಥಿತಿ ಇದೆ. "
        f"ಬೆಳೆ ಉಳಿಸಲು ತಕ್ಷಣ ದಿನಕ್ಕೆ {daily_txt} ಲೀಟರ್ ನೀರು ಅಗತ್ಯವಿದೆ. "
        "ಬೋರ್‌ವೆಲ್‌ಗೆ ಹಾನಿಯಾಗದಂತೆ ಮಿತ ನೀರಾವರಿ ಮಾಡಿ. "
        "ಈಗಲೇ ಬೆಳೆ ವಿಮೆ ದಾವೆ ಸಲ್ಲಿಸಿ ಹೊಲದ ಫೋಟೋ ತೆಗೆಯಿರಿ."
    )


def synthesize_kannada_gtts(text_kn: str) -> str | None:
    """
    Synthesize real spoken Kannada MP3 audio using gTTS(lang='kn').
    Returns base64-encoded MP3 string or None when offline/unavailable.
    """
    if not _GTTS_AVAILABLE or not text_kn.strip():
        return None
    try:
        tts = gTTS(text=text_kn, lang="kn", slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        raw = buf.getvalue()
        if not raw:
            return None
        return base64.b64encode(raw).decode("ascii")
    except Exception as exc:
        logger.warning("gTTS Kannada synthesis unavailable (%s); using browser TTS.", exc)
        return None


def generate_tts_advisory(
    farmer_name: str,
    crop_type: str,
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndvi: float,
    ndmi: float,
) -> tuple[str | None, str, str, str]:
    """
    Generate Kannada text advisory and optional gTTS spoken MP3 audio.
    Returns (audio_base64, audio_mime, audio_source, advisory_text_kn).
    """
    advisory_kn = build_kannada_advisory_text(
        drought_stage=drought_stage,
        et0=et0,
        survival_liters=survival_liters,
        ndmi=ndmi,
        crop_type=crop_type,
    )
    audio_b64 = synthesize_kannada_gtts(advisory_kn)
    if audio_b64:
        return audio_b64, "audio/mpeg", "gtts_kn", advisory_kn
    return None, "text/plain", "browser_tts", advisory_kn


def generate_voice_advisory(
    farmer_name: str,
    crop_type: str,
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndvi: float,
    ndmi: float,
) -> tuple[str | None, str]:
    """Compatibility wrapper returning (audio_base64, advisory_text_kn)."""
    audio_b64, _mime, _src, advisory_kn = generate_tts_advisory(
        farmer_name=farmer_name,
        crop_type=crop_type,
        drought_stage=drought_stage,
        et0=et0,
        survival_liters=survival_liters,
        ndvi=ndvi,
        ndmi=ndmi,
    )
    return audio_b64, advisory_kn
