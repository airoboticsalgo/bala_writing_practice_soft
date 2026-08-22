"""Writing-line guides and the vertical metrics everything else derives from."""

from __future__ import annotations

from dataclasses import dataclass

from .fonts import LoadedFont
from .glyphs import headline_units, probe_bottom, probe_top
from .paint import gray_for

#: How a single guide line is drawn.
LINE_SOLID = "solid"
LINE_DASHED = "dashed"
LINE_DOTTED = "dotted"

#: The user's choice for *all* guide lines. ``classic`` keeps the per-line
#: convention below (base and top solid, the ones you only aim at dashed);
#: ``four`` uses solid outer lines and dashed inner ones; anything else
#: overrides every line with the same style, including the base line.
CLASSIC = "classic"
FOUR = "four"
GUIDE_STYLES = (CLASSIC, FOUR, LINE_SOLID, LINE_DASHED, LINE_DOTTED)

# Probe characters, in fallback order, used to measure each guide position.
ASCENDER_PROBES = "bdhkl"
XHEIGHT_PROBES = "xzvo"
DESCENDER_PROBES = "pqgyj"
MATRA_UP_PROBES = "ीैेो"
MATRA_DOWN_PROBES = "ुूृ"


@dataclass(frozen=True)
class RowMetrics:
    """All offsets are in points, relative to the base line of a row."""

    scale: float
    top: float  # English top (ascender) line / Hindi shiro-rekha == line_height
    mid: float  # English x-height line
    upper: float  # Hindi upper-matra line, above the headline
    descender: float  # negative: below the base line

    @property
    def ascent(self) -> float:
        return max(self.top, self.upper)

    @property
    def descent(self) -> float:
        return abs(self.descender)

    @property
    def height(self) -> float:
        return self.ascent + self.descent


def compute_metrics(font: LoadedFont, lang: str, line_height_pt: float) -> RowMetrics:
    """Derive every guide position from one scale factor.

    English: ``line_height`` is base line -> ascender (top) line.
    Hindi: ``line_height`` is base line -> shiro-rekha, i.e. the letter body
    height, because that is the part of a Devanagari letter a child writes.
    """
    if lang == "hindi":
        reference = headline_units(font)
        scale = line_height_pt / reference
        upper = (probe_top(font, MATRA_UP_PROBES) or font.ascender) * scale
        below = probe_bottom(font, MATRA_DOWN_PROBES) or font.descender
        return RowMetrics(
            scale=scale,
            top=line_height_pt,
            mid=0.0,
            upper=max(upper, line_height_pt),
            descender=below * scale,
        )

    reference = probe_top(font, ASCENDER_PROBES) or font.ascender
    scale = line_height_pt / reference
    mid = (probe_top(font, XHEIGHT_PROBES) or font.x_height) * scale
    below = probe_bottom(font, DESCENDER_PROBES) or font.descender
    return RowMetrics(
        scale=scale,
        top=line_height_pt,
        mid=mid,
        upper=0.0,
        descender=below * scale,
    )


def row_pitch(metrics: RowMetrics, line_spacing: str, line_height_pt: float) -> float:
    """Distance between consecutive base lines."""
    gap = line_height_pt * 0.45
    pitch = metrics.height + gap
    if line_spacing == "double":
        pitch += metrics.height + gap
    return pitch


def guide_dash(metrics: RowMetrics) -> float:
    return max(1.2, metrics.top / 8.0)


def guide_dot(metrics: RowMetrics) -> float:
    """Gap between the dots of a dotted guide line.

    A dot has no length of its own (see :func:`app.render.paint._apply_style`),
    so the gap alone sets the rhythm and has to be tighter than a dash period.
    """
    return max(1.0, metrics.top / 11.0)


def guide_offsets(
    lang: str,
    metrics: RowMetrics,
    *,
    guide_style: str = CLASSIC,
    top_line: bool = False,
    mid_line: bool = False,
    descender_line: bool = False,
    shiro_rekha: bool = False,
    upper_matra_line: bool = False,
    lower_matra_line: bool = False,
) -> list[tuple[float, str]]:
    """Guide positions as (offset from base line, line style).

    The base line is always included; everything else is opt-in. Single source of
    truth, shared by the PDF renderer and the SVG previews.
    """
    if guide_style == FOUR:
        # Four-line: outer boundaries solid, inner guides dashed.
        offsets: list[tuple[float, str]] = [(0.0, LINE_DASHED)]
        if lang == "hindi":
            if shiro_rekha:
                offsets.append((metrics.top, LINE_SOLID))
            if upper_matra_line and metrics.upper > metrics.top:
                offsets.append((metrics.upper, LINE_DASHED))
            if lower_matra_line:
                offsets.append((metrics.descender, LINE_SOLID))
        else:
            if top_line:
                offsets.append((metrics.top, LINE_SOLID))
            if mid_line:
                offsets.append((metrics.mid, LINE_DASHED))
            if descender_line:
                offsets.append((metrics.descender, LINE_SOLID))
        return offsets

    offsets: list[tuple[float, str]] = [(0.0, LINE_SOLID)]
    if lang == "hindi":
        if shiro_rekha:
            offsets.append((metrics.top, LINE_SOLID))
        if upper_matra_line and metrics.upper > metrics.top:
            offsets.append((metrics.upper, LINE_DASHED))
        if lower_matra_line:
            offsets.append((metrics.descender, LINE_DASHED))
    else:
        if top_line:
            offsets.append((metrics.top, LINE_SOLID))
        if mid_line:
            offsets.append((metrics.mid, LINE_DASHED))
        if descender_line:
            offsets.append((metrics.descender, LINE_SOLID))
    if guide_style in (LINE_SOLID, LINE_DASHED, LINE_DOTTED):
        return [(offset, guide_style) for offset, _ in offsets]
    return offsets


def draw_row_guides(
    canvas,
    *,
    lang: str,
    metrics: RowMetrics,
    x0: float,
    x1: float,
    baseline_y: float,
    darkness: float,
    thickness: float,
    guide_style: str = CLASSIC,
    **flags: bool,
) -> None:
    dash = guide_dash(metrics)
    dot = guide_dot(metrics)
    canvas.saveState()
    try:
        canvas.setStrokeGray(gray_for(darkness))
        canvas.setLineWidth(thickness)
        for offset, style in guide_offsets(
            lang, metrics, guide_style=guide_style, **flags
        ):
            canvas.saveState()
            if style == LINE_DASHED:
                canvas.setDash([dash, dash])
            elif style == LINE_DOTTED:
                canvas.setLineCap(1)
                canvas.setDash([0, dot])
            canvas.line(x0, baseline_y + offset, x1, baseline_y + offset)
            canvas.restoreState()
    finally:
        canvas.restoreState()
