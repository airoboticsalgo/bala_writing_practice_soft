"""Glyph outline extraction.

Dashed and outlined letters need the glyph *outline*, not a glyph bitmap: you
cannot dash or variable-stroke a rasterised letter.  ``fontTools``' ``BasePen``
gives us that -- it resolves composite glyphs and converts TrueType quadratics
to cubics, so a contour is only ever moveTo / lineTo / curveTo / close.

Outlines are cached per (font, glyph id).  A worksheet repeats the same handful
of glyphs hundreds of times, so without the cache 5,000 characters crawls.
"""

from __future__ import annotations

from functools import lru_cache

from fontTools.pens.basePen import BasePen

from .fonts import LoadedFont

# A contour is a list of segments in font units:
#   ("m", (x, y))
#   ("l", (x, y))
#   ("c", (x1, y1), (x2, y2), (x3, y3))
Contour = list[tuple]


class OutlinePen(BasePen):
    """Collects glyph outlines as plain tuples."""

    def __init__(self, glyph_set):
        super().__init__(glyph_set)
        self.contours: list[Contour] = []
        self._current: Contour | None = None

    def _moveTo(self, pt):
        self._current = [("m", pt)]
        self.contours.append(self._current)

    def _lineTo(self, pt):
        if self._current is not None:
            self._current.append(("l", pt))

    def _curveToOne(self, pt1, pt2, pt3):
        if self._current is not None:
            self._current.append(("c", pt1, pt2, pt3))

    def _closePath(self):
        self._current = None

    def _endPath(self):
        self._current = None


def _contours_for_name(font: LoadedFont, glyph_name: str) -> list[Contour]:
    pen = OutlinePen(font.glyph_set)
    try:
        font.glyph_set[glyph_name].draw(pen)
    except KeyError:
        return []
    return pen.contours


@lru_cache(maxsize=8192)
def glyph_contours(font: LoadedFont, gid: int) -> tuple[Contour, ...]:
    """Outline of ``gid`` in font units. Empty for blanks such as ``space``."""
    try:
        glyph_name = font.glyph_order[gid]
    except IndexError:
        return ()
    return tuple(_contours_for_name(font, glyph_name))


@lru_cache(maxsize=256)
def ink_extents(font: LoadedFont, char: str) -> tuple[float, float] | None:
    """(ymin, ymax) of ``char``'s outline in font units, or None if it has none.

    Guide lines are derived from measured ink, not from table metrics.  The
    ``hhea`` ascender is unusable for this: Andika reports 2500 on a 2048 em
    because it bakes in line gap, which would render "12 mm letters" as 6.7 mm.
    """
    glyph_name = font.cmap.get(ord(char))
    if not glyph_name:
        return None
    ys = [
        pt[1]
        for contour in _contours_for_name(font, glyph_name)
        for seg in contour
        for pt in seg[1:]
    ]
    return (min(ys), max(ys)) if ys else None


def probe_top(font: LoadedFont, chars: str) -> float | None:
    """Ink top of the first of ``chars`` that has an outline."""
    for char in chars:
        extents = ink_extents(font, char)
        if extents and extents[1] > 0:
            return extents[1]
    return None


def probe_bottom(font: LoadedFont, chars: str) -> float | None:
    """Ink bottom of the first of ``chars`` that dips below the base line."""
    for char in chars:
        extents = ink_extents(font, char)
        if extents and extents[0] < 0:
            return extents[0]
    return None


def headline_units(font: LoadedFont) -> float:
    """Height of the Devanagari headline (shiro-rekha) in font units.

    Deliberately *not* the font ascender: the ascender leaves room for upper
    matras, so using it would float the guide above the letters -- the most
    visible possible bug on a Hindi worksheet.  The top edge of a bare consonant
    *is* the headline.
    """
    return probe_top(font, "कपभ") or font.x_height * 1.2
