"""Font discovery, loading and metrics.

A :class:`LoadedFont` bundles everything the renderer needs: the HarfBuzz font
used for shaping, the fontTools glyph set used for outlines, and the vertical
metrics used to place guide lines.  Fonts are cached by path because a single
worksheet touches the same font thousands of times.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import uharfbuzz as hb
from fontTools.ttLib import TTFont

#: Sample characters used to decide which script a font can be used for.
LATIN_PROBE = "Ag"
DEVANAGARI_PROBE = "कि"

#: Readable names for the bundled fonts. A camel-case splitter would turn
#: "ABeeZee" into "A Bee Zee", so the few names we ship are simply listed.
DISPLAY_NAMES = {
    "Andika-Regular.ttf": "Andika",
    "ABeeZee-Regular.ttf": "ABeeZee",
    "NotoSansDevanagari-Regular.ttf": "Noto Sans Devanagari",
    "Mukta-Regular.ttf": "Mukta",
    "LucidaHandwriting-Regular.ttf": "Lucida Handwriting",
    "LucidaSans-Regular.ttf": "Lucida Sans",
    "LucidaSansItalic-Regular.ttf": "Lucida Sans Italic",
    "LucidaSansDemibold-Regular.ttf": "Lucida Sans Demibold",
    "LucidaSansDemiboldItalic-Regular.ttf": "Lucida Sans Demibold Italic",
    "LucidaSansTypewriter-Regular.ttf": "Lucida Sans Typewriter",
}


@dataclass(frozen=True)
class LoadedFont:
    path: Path
    upem: int
    ascender: int
    descender: int
    x_height: int
    cap_height: int
    # compare=False keeps LoadedFont hashable despite the unhashable members,
    # so it can be passed to lru_cache-decorated helpers.
    hb_font: Any = field(repr=False, compare=False)
    glyph_order: list[str] = field(repr=False, compare=False)
    glyph_set: Any = field(repr=False, compare=False)
    cmap: dict[int, str] = field(repr=False, compare=False)

    @property
    def file_name(self) -> str:
        return self.path.name

    @property
    def label(self) -> str:
        return DISPLAY_NAMES.get(
            self.path.name, self.path.stem.replace("-Regular", "").replace("-", " ")
        )

    def supports(self, text: str) -> bool:
        return all(ord(ch) in self.cmap for ch in text)


@lru_cache(maxsize=16)
def load_font(path: str | Path) -> LoadedFont:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Font not found: {path}")

    blob = hb.Blob.from_file_path(str(path))
    face = hb.Face(blob)
    hb_font = hb.Font(face)

    tt = TTFont(str(path), fontNumber=0, lazy=True)
    upem = tt["head"].unitsPerEm
    hhea = tt["hhea"]
    os2 = tt["OS/2"] if "OS/2" in tt else None

    x_height = getattr(os2, "sxHeight", 0) or 0
    if x_height <= 0:
        x_height = round(upem * 0.5)
    cap_height = getattr(os2, "sCapHeight", 0) or 0
    if cap_height <= 0:
        cap_height = round(upem * 0.7)

    return LoadedFont(
        path=path,
        upem=upem,
        ascender=hhea.ascender,
        descender=hhea.descender,
        x_height=x_height,
        cap_height=cap_height,
        hb_font=hb_font,
        glyph_order=tt.getGlyphOrder(),
        glyph_set=tt.getGlyphSet(),
        cmap=tt.getBestCmap(),
    )


def available_fonts(fonts_dir: Path) -> list[LoadedFont]:
    """Every usable .ttf in ``fonts_dir``, sorted by display label."""
    if not fonts_dir.is_dir():
        return []
    found = []
    for candidate in sorted(fonts_dir.glob("*.ttf")):
        if candidate.name.startswith("_"):
            continue
        try:
            found.append(load_font(candidate))
        except Exception:  # a corrupt font must not take the whole app down
            continue
    return sorted(found, key=lambda f: f.label)


def fonts_for_language(fonts_dir: Path, lang: str) -> list[LoadedFont]:
    probe = DEVANAGARI_PROBE if lang == "hindi" else LATIN_PROBE
    return [f for f in available_fonts(fonts_dir) if f.supports(probe)]


def resolve_font(fonts_dir: Path, lang: str, requested: str | None, default: str) -> LoadedFont:
    """Pick the requested font if it is valid for ``lang``, else the default."""
    usable = fonts_for_language(fonts_dir, lang)
    if not usable:
        raise RuntimeError(
            f"No font in {fonts_dir} can render {lang!r}. Expected e.g. {default}."
        )
    by_name = {f.file_name: f for f in usable}
    if requested and requested in by_name:
        return by_name[requested]
    return by_name.get(default, usable[0])


def check_startup(fonts_dir: Path, english_default: str, hindi_default: str) -> list[str]:
    """Validate the font setup at boot; returns human-readable notes."""
    if not fonts_dir.is_dir():
        raise RuntimeError(f"Fonts directory missing: {fonts_dir}")

    notes = []
    for lang, default in (("english", english_default), ("hindi", hindi_default)):
        usable = fonts_for_language(fonts_dir, lang)
        if not usable:
            raise RuntimeError(
                f"No {lang} font found in {fonts_dir}. Expected {default} "
                f"(see app/static/fonts/README or PROMPT.md section 5)."
            )
        names = [f.file_name for f in usable]
        if default not in names:
            notes.append(
                f"{lang}: default {default} missing from {fonts_dir}; using {names[0]}"
            )
        else:
            notes.append(f"{lang}: {default} ({len(names)} font(s) available)")
    return notes
