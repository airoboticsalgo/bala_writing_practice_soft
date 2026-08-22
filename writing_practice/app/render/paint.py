"""Painting shaped glyph outlines onto a ReportLab canvas.

Letter styles map onto path painting operations:

``solid``     fill, non-zero winding so counters (o, a, ठ) stay hollow; a non-zero
              ``weight`` also strokes the outline, which fattens the letter
``outlined``  stroke only, width = letter thickness
``dashed``    stroke only with a PDF dash array -- dashes follow beziers natively
``dotted``    stroke only with a zero-length dash and a round cap, which is how
              PDF draws a row of dots; each dot's diameter is the line width

Worksheet letters go through :class:`GlyphPainter`, which emits each distinct
glyph once as a Form XObject and then just invokes it. Headers use
:func:`draw_text`, which inlines the path -- they are a handful of glyphs and
they use a different size and style from the practice rows.
"""

from __future__ import annotations

from reportlab.pdfgen.canvas import FILL_NON_ZERO

from .fonts import LoadedFont
from .glyphs import glyph_contours
from .shaper import shape

SOLID = "solid"
OUTLINED = "outlined"
DASHED = "dashed"
DOTTED = "dotted"
LETTER_STYLES = (DASHED, DOTTED, OUTLINED, SOLID)
#: Styles drawn by stroking the outline, i.e. the ones ``thickness`` applies to.
STROKE_STYLES = (DASHED, DOTTED, OUTLINED)

_BBOX_PADDING = 10.0  # font units, keeps a form's BBox off the outline

#: Dash and dot periods as a fraction of the line height, so tracing marks keep
#: their proportions at every letter size. Tuned by eye: long dashes shatter
#: Devanagari conjuncts into unrecognisable fragments, and dots need a wider
#: period than dashes because a dot contributes no length of its own.
DASH_DIVISOR = 24.0
DOT_DIVISOR = 14.0

#: Multipliers for the user's "trace spacing" choice.
SPACING_FACTORS = {"tight": 0.7, "normal": 1.0, "wide": 1.5}


def trace_periods(line_height_pt: float, spacing: str = "normal") -> tuple[float, float]:
    """(dash period, dot period) in points for a given line height.

    Shared by the PDF renderer and the SVG previews so the two cannot drift.
    """
    factor = SPACING_FACTORS.get(spacing, 1.0)
    return (
        max(0.6, line_height_pt / DASH_DIVISOR) * factor,
        max(0.8, line_height_pt / DOT_DIVISOR) * factor,
    )


def gray_for(darkness_pct: float) -> float:
    """Percent black -> ReportLab gray level (1.0 = white, 0.0 = black)."""
    return max(0.0, min(1.0, 1.0 - darkness_pct / 100.0))


def text_width(font: LoadedFont, text: str, scale: float) -> float:
    return shape(font, text)[1] * scale


def _add_contours(path, contours, origin_x: float, origin_y: float, scale: float) -> bool:
    has_ink = False
    for contour in contours:
        has_ink = True
        for segment in contour:
            if segment[0] == "m":
                path.moveTo(
                    origin_x + segment[1][0] * scale, origin_y + segment[1][1] * scale
                )
            elif segment[0] == "l":
                path.lineTo(
                    origin_x + segment[1][0] * scale, origin_y + segment[1][1] * scale
                )
            else:
                (x1, y1), (x2, y2), (x3, y3) = segment[1], segment[2], segment[3]
                path.curveTo(
                    origin_x + x1 * scale,
                    origin_y + y1 * scale,
                    origin_x + x2 * scale,
                    origin_y + y2 * scale,
                    origin_x + x3 * scale,
                    origin_y + y3 * scale,
                )
        path.close()
    return has_ink


def _paint(canvas, path, style: str, weight: float = 0.0) -> None:
    if style == SOLID:
        # ReportLab defaults to even-odd fill; TrueType outlines rely on
        # non-zero winding, so overlapping contours (common in Devanagari
        # conjuncts) would otherwise be punched out of the letter.
        # Stroking on top of the fill is what ``weight`` does: it grows the
        # letter outwards by half the line width, a poor man's bold.
        canvas.drawPath(
            path, stroke=1 if weight > 0 else 0, fill=1, fillMode=FILL_NON_ZERO
        )
    else:
        canvas.drawPath(path, stroke=1, fill=0)


def _apply_style(
    canvas,
    style: str,
    darkness: float,
    thickness: float,
    dash_period: float,
    scale: float = 1.0,
    *,
    dot_period: float | None = None,
    weight: float = 0.0,
    trace_layers: str = "single",
) -> None:
    """Set colour, stroke width and dash. ``scale`` divides out a scaled CTM:
    PDF line widths and dashes are measured in the user space in force when the
    path is stroked, so a glyph drawn under a scale matrix needs them shrunk."""
    gray = gray_for(darkness)
    if style == SOLID:
        canvas.setFillGray(gray)
        if weight > 0:
            canvas.setStrokeGray(gray)
            canvas.setLineWidth(weight / scale)
            canvas.setLineJoin(1)
            canvas.setLineCap(1)
        return
    canvas.setStrokeGray(gray)
    canvas.setLineWidth(thickness / scale)
    canvas.setLineJoin(1)
    canvas.setLineCap(1)
    if style == DASHED:
        period = dash_period / scale
        if trace_layers == "double":
            # Two short dashes per cycle. The intra-pair gap scales with the
            # line thickness so the rounded caps don't merge at print size.
            small_frac = min(0.85, max(0.3, (thickness + 0.2) / dash_period))
            mark_frac = (2.0 - 1.0 - small_frac) / 2.0
            canvas.setDash(
                [mark_frac * period, small_frac * period, mark_frac * period, 1.0 * period]
            )
        else:
            canvas.setDash([period, period])
    elif style == DOTTED:
        # A zero-length dash under a round cap paints a filled circle of the
        # line width; the gap alone controls how far apart the dots sit.
        gap = (dot_period if dot_period is not None else dash_period * 2) / scale
        if trace_layers == "double":
            # Two dots per dot-period. Keep them distinct from each other and
            # from the next pair, falling back toward a single dot if there
            # isn't room for two at this thickness/dot-period combination.
            micro_pt = min(
                max(dot_period * 0.45, thickness + 0.1),
                max(0.0, dot_period - thickness - 0.1),
            )
            micro = (micro_pt / dot_period) * gap
            canvas.setDash([0, micro, 0, gap - micro])
        else:
            canvas.setDash([0, gap])


def draw_text(
    canvas,
    font: LoadedFont,
    text: str,
    x: float,
    baseline_y: float,
    scale: float,
    *,
    style: str = SOLID,
    darkness: float = 100.0,
    thickness: float = 0.6,
    dash_period: float = 1.5,
    dot_period: float | None = None,
    weight: float = 0.0,
    trace_layers: str = "single",
) -> float:
    """Draw ``text`` inline with its baseline at ``baseline_y``; advance in pt."""
    glyphs, advance = shape(font, text)
    path = canvas.beginPath()
    has_ink = False
    for glyph in glyphs:
        has_ink |= _add_contours(
            path,
            glyph_contours(font, glyph.gid),
            x + glyph.x * scale,
            baseline_y + glyph.y * scale,
            scale,
        )
    if not has_ink:
        return advance * scale

    canvas.saveState()
    try:
        _apply_style(
            canvas,
            style,
            darkness,
            thickness,
            dash_period,
            dot_period=dot_period,
            weight=weight,
            trace_layers=trace_layers,
        )
        _paint(canvas, path, style, weight)
    finally:
        canvas.restoreState()
    return advance * scale


class GlyphPainter:
    """Draws practice text by reusing one Form XObject per distinct glyph.

    Inlining every glyph's bezier path works but is wasteful: a worksheet redraws
    the same few dozen glyphs thousands of times, which made a 5,000-character
    sheet a 5 MB file that took seconds to write. A form is defined once and then
    invoked with a translate/scale matrix, exactly how embedded fonts work.
    """

    def __init__(
        self,
        font: LoadedFont,
        scale: float,
        *,
        style: str,
        darkness: float,
        thickness: float,
        dash_period: float,
        dot_period: float | None = None,
        weight: float = 0.0,
        trace_layers: str = "single",
    ):
        self.font = font
        self.scale = scale
        self.style = style
        self.darkness = darkness
        self.thickness = thickness
        self.dash_period = dash_period
        self.dot_period = dot_period
        self.weight = weight
        self.trace_layers = trace_layers
        self._used: dict[int, str] = {}

    def draw(self, canvas, text: str, x: float, baseline_y: float) -> float:
        glyphs, advance = shape(self.font, text)
        drawable = [g for g in glyphs if glyph_contours(self.font, g.gid)]
        if not drawable:
            return advance * self.scale

        canvas.saveState()
        try:
            _apply_style(
                canvas,
                self.style,
                self.darkness,
                self.thickness,
                self.dash_period,
                self.scale,
                dot_period=self.dot_period,
                weight=self.weight,
                trace_layers=self.trace_layers,
            )
            canvas.translate(x, baseline_y)
            canvas.scale(self.scale, self.scale)
            for glyph in drawable:
                name = self._register(glyph.gid)
                canvas.saveState()
                canvas.translate(glyph.x, glyph.y)
                canvas.doForm(name)
                canvas.restoreState()
        finally:
            canvas.restoreState()
        return advance * self.scale

    def finalize(self, canvas) -> None:
        """Define every glyph form used. Call after the last page, before save."""
        for gid, name in self._used.items():
            contours = glyph_contours(self.font, gid)
            canvas.beginForm(name, *self._bbox(contours))
            path = canvas.beginPath()
            _add_contours(path, contours, 0.0, 0.0, 1.0)
            _paint(canvas, path, self.style, self.weight)
            canvas.endForm()

    def _register(self, gid: int) -> str:
        name = self._used.get(gid)
        if name is None:
            name = f"wpGlyph{gid}"
            self._used[gid] = name
        return name

    def _bbox(self, contours) -> tuple[float, float, float, float]:
        """A form's BBox clips it, so derive it from the outline and pad it.

        The pad also covers the stroke, which straddles the outline.
        """
        xs = [pt[0] for contour in contours for seg in contour for pt in seg[1:]]
        ys = [pt[1] for contour in contours for seg in contour for pt in seg[1:]]
        ink = self.weight if self.style == SOLID else self.thickness
        pad = _BBOX_PADDING + ink / self.scale
        return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
