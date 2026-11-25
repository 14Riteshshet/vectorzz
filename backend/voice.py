"""
Compatibility shim re-exporting Kannada advisory helpers from backend.tts.
"""

from backend.tts import (
    build_kannada_advisory_text,
    generate_voice_advisory,
    localize_crop_kn,
)

__all__ = [
    "build_kannada_advisory_text",
    "generate_voice_advisory",
    "localize_crop_kn",
]
