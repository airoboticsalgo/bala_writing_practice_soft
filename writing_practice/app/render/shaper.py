"""HarfBuzz text shaping.

This is what makes Devanagari correct: matras that are typed after a consonant
but drawn before it (``कि``) get reordered, and conjuncts (``क्ष``, ``त्र``) are
replaced by ligature glyphs.  All coordinates are in font units.
"""

from __future__ import annotations

from dataclasses import dataclass

import uharfbuzz as hb

from .fonts import LoadedFont


@dataclass(frozen=True, slots=True)
class PositionedGlyph:
    gid: int
    x: float
    y: float


def shape(font: LoadedFont, text: str) -> tuple[list[PositionedGlyph], float]:
    """Shape ``text``; returns positioned glyphs and the total advance width."""
    if not text:
        return [], 0.0

    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font.hb_font, buf)

    glyphs: list[PositionedGlyph] = []
    pen_x = pen_y = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs.append(
            PositionedGlyph(info.codepoint, pen_x + pos.x_offset, pen_y + pos.y_offset)
        )
        pen_x += pos.x_advance
        pen_y += pos.y_advance
    return glyphs, pen_x


def advance_width(font: LoadedFont, text: str) -> float:
    """Total advance of ``text`` in font units (used for wrapping and centring)."""
    return shape(font, text)[1]
