"""Configuration loading for writing_practice.

Every key has an in-code default so the app boots with a missing or partial
``config/app.conf``.  Override the file location with the environment variable
``WRITING_PRACTICE_CONFIG``.
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "app.conf"

DEFAULTS: dict[str, dict[str, str]] = {
    "server": {
        "host": "127.0.0.1",
        "port": "5050",
        "debug": "true",
    },
    "worksheet": {
        "page_title": "Handwriting Practice",
        "paper_size": "A4",
        "orientation": "tall",
        "margin_mm": "12",
        "max_text_chars": "5000",
        "line_height_mm": "12",
        "rows_per_block": "3",
        "line_spacing": "single",
        "following_lines": "repeat",
    },
    "guides": {
        "darkness": "30",
        "thickness": "0.5",
        "style": "classic",
        "english_top_line": "true",
        "english_mid_line": "true",
        "english_descender_line": "false",
        "hindi_shiro_rekha": "true",
        "hindi_upper_matra_line": "true",
        "hindi_lower_matra_line": "false",
    },
    "letters": {
        "style": "dashed",
        "darkness": "50",
        "thickness": "0.6",
        "solid_layers": "single",
        "solid_weight": "0",
        "trace_layers": "single",
        "trace_spacing": "normal",
    },
    "fonts": {
        "fonts_dir": "app/static/fonts",
        "english_default": "Andika-Regular.ttf",
        "hindi_default": "NotoSansDevanagari-Regular.ttf",
    },
    "output": {
        "save_generated": "false",
        "output_dir": "output",
    },
}


class Settings:
    """Thin typed wrapper over :class:`configparser.ConfigParser`."""

    def __init__(self, parser: configparser.ConfigParser, source: Path | None = None):
        self._parser = parser
        self.source = source

    def get(self, section: str, key: str) -> str:
        return self._parser.get(section, key, fallback=DEFAULTS[section][key])

    def int(self, section: str, key: str) -> int:
        try:
            return self._parser.getint(section, key)
        except (ValueError, configparser.Error):
            return int(DEFAULTS[section][key])

    def float(self, section: str, key: str) -> float:
        try:
            return self._parser.getfloat(section, key)
        except (ValueError, configparser.Error):
            return float(DEFAULTS[section][key])

    def bool(self, section: str, key: str) -> bool:
        try:
            return self._parser.getboolean(section, key)
        except (ValueError, configparser.Error):
            return DEFAULTS[section][key] == "true"

    def path(self, section: str, key: str) -> Path:
        value = Path(self.get(section, key))
        return value if value.is_absolute() else PROJECT_ROOT / value


def load_settings(path: str | os.PathLike[str] | None = None) -> Settings:
    parser = configparser.ConfigParser()
    parser.read_dict(DEFAULTS)

    candidate = path or os.environ.get("WRITING_PRACTICE_CONFIG") or DEFAULT_CONFIG_PATH
    candidate = Path(candidate)
    read = parser.read(candidate, encoding="utf-8")
    return Settings(parser, candidate if read else None)
