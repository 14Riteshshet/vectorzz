"""
SookshmaJal – Kannada Crop Water Advisory Generator.
Builds natural, localized Kannada farmer guidance with short sentences
and clear pauses (text-only, no broken audio players or external TTS calls).
"""

from __future__ import annotations

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
    pauses, keeping raw technical numbers out of the sentence body.
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


def generate_voice_advisory(
    farmer_name: str,
    crop_type: str,
    drought_stage: str,
    et0: float,
    survival_liters: float,
    ndvi: float,
    ndmi: float,
) -> tuple[None, str]:
    """Text-only Kannada advisory helper returning (None, advisory_text_kn)."""
    advisory_kn = build_kannada_advisory_text(
        drought_stage=drought_stage,
        et0=et0,
        survival_liters=survival_liters,
        ndmi=ndmi,
        crop_type=crop_type,
    )
    return None, advisory_kn
