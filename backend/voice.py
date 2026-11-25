"""
Compatibility shim re-exporting Kannada TTS helpers from backend.tts.
"""

from backend.tts import (
    build_kannada_advisory_text,
    generate_tts_advisory,
    generate_voice_advisory,
    localize_crop_kn,
    synthesize_kannada_gtts,
)

__all__ = [
    "build_kannada_advisory_text",
    "generate_tts_advisory",
    "generate_voice_advisory",
    "localize_crop_kn",
    "synthesize_kannada_gtts",
]
