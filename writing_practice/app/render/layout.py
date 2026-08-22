"""Line wrapping, row building and pagination.

Wrapping is measured from real shaped advance widths, never an estimated
character count -- a Devanagari cluster and an ``i`` are nothing alike.
"""

from __future__ import annotations

from dataclasses import dataclass

from .fonts import LoadedFont
from .shaper import advance_width


@dataclass(frozen=True, slots=True)
class Row:
    """One writing line. Empty ``text`` means a ruled but blank row."""

    text: str


class _Measurer:
    """Caches measurements; the same words recur constantly on a worksheet."""

    def __init__(self, font: LoadedFont, scale: float):
        self._font = font
        self._scale = scale
        self._cache: dict[str, float] = {}

    def width(self, text: str) -> float:
        cached = self._cache.get(text)
        if cached is None:
            cached = advance_width(self._font, text) * self._scale
            self._cache[text] = cached
        return cached


def _break_long_word(word: str, measure: _Measurer, max_width: float) -> list[str]:
    pieces: list[str] = []
    current = ""
    for char in word:
        candidate = current + char
        if current and measure.width(candidate) > max_width:
            pieces.append(current)
            current = char
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def wrap_line(
    font: LoadedFont, text: str, scale: float, max_width: float
) -> list[str]:
    """Greedy wrap on whitespace; hard-break only words wider than a whole line."""
    measure = _Measurer(font, scale)
    if not text.strip():
        return [""]
    if measure.width(text) <= max_width:
        return [text]

    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        if not word:
            continue
        candidate = f"{current} {word}" if current else word
        if measure.width(candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        if measure.width(word) <= max_width:
            current = word
        else:
            pieces = _break_long_word(word, measure, max_width)
            lines.extend(pieces[:-1])
            current = pieces[-1] if pieces else ""
    if current:
        lines.append(current)
    return lines or [""]


def build_rows(
    text: str,
    font: LoadedFont,
    scale: float,
    max_width: float,
    *,
    rows_per_block: int,
    following_lines: str,
) -> list[Row]:
    """Expand the typed text into the sequence of writing lines to draw.

    A blank input line yields one blank row -- it is a deliberate free-practice
    line, not something to skip.
    """
    rows: list[Row] = []
    for line in text.split("\n"):
        if not line.strip():
            rows.append(Row(""))
            continue
        for segment in wrap_line(font, line.strip(), scale, max_width):
            rows.append(Row(segment))
            repeat = segment if following_lines == "repeat" else ""
            rows.extend(Row(repeat) for _ in range(rows_per_block - 1))
    return rows


def rows_per_page(available_height: float, pitch: float, row_height: float) -> int:
    """How many rows fit; the last row needs no trailing gap."""
    if pitch <= 0:
        return 1
    count = int(available_height // pitch)
    if available_height - count * pitch >= row_height:
        count += 1
    return max(1, count)


def paginate(rows: list[Row], per_page: int) -> list[list[Row]]:
    if not rows:
        return [[]]
    return [rows[i : i + per_page] for i in range(0, len(rows), per_page)]
