"""Preset practice content, kept out of the templates."""

from .english_presets import ENGLISH_PRESETS
from .hindi_presets import HINDI_PRESETS

PRESETS = {"english": ENGLISH_PRESETS, "hindi": HINDI_PRESETS}

__all__ = ["PRESETS", "ENGLISH_PRESETS", "HINDI_PRESETS"]
