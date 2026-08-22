"""SVG previews of what an option will look like on the printed sheet.

These reuse the PDF pipeline -- the same shaping, the same cached glyph outlines,
the same guide positions and row pitch -- so a preview cannot drift away from the
worksheet it is previewing. SVG (rather than a raster thumbnail) means no image
library, no rasterizer, and crisp samples at any size.

Glyphs go into ``<defs>`` once and are placed with ``<use>``, the same reuse
trick the PDF renderer does with Form XObjects.
"""

from __future__ import annotations

from functools import lru_cache

from .fonts import LoadedFont, load_font
from .glyphs import glyph_contours
from .guides import (
    LINE_DASHED,
    LINE_DOTTED,
    compute_metrics,
    guide_dash,
    guide_dot,
    guide_offsets,
    row_pitch,
)
from .layout import build_rows
from .paint import DASHED, DOTTED, SOLID, gray_for, trace_periods
from .shaper import shape
from .spec import WorksheetSpec

TEXT_INSET = 2.0  # pt, matches the PDF renderer
VERTICAL_PAD = 2.0


def _num(value: float) -> str:
    """Compact number: font units are usually integers."""
    rounded = round(value, 2)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)


def _rgb(darkness: float) -> str:
    level = round(gray_for(darkness) * 255)
    return f"rgb({level},{level},{level})"


@lru_cache(maxsize=8192)
def glyph_path_d(font: LoadedFont, gid: int) -> str:
    """SVG path data for a glyph, in font units with y pointing up."""
    parts: list[str] = []
    for contour in glyph_contours(font, gid):
        for segment in contour:
            if segment[0] == "m":
                parts.append(f"M{_num(segment[1][0])} {_num(segment[1][1])}")
            elif segment[0] == "l":
                parts.append(f"L{_num(segment[1][0])} {_num(segment[1][1])}")
            else:
                coords = " ".join(
                    f"{_num(point[0])} {_num(point[1])}" for point in segment[1:]
                )
                parts.append(f"C{coords}")
        parts.append("Z")
    return " ".join(parts)


def _letter_style_attrs(
    spec: WorksheetSpec, scale: float, dash_period: float, dot_period: float
) -> str:
    """Fill/stroke attributes. Stroke widths are divided by the scale because the
    glyph group is scaled, exactly as in the PDF renderer."""
    colour = _rgb(spec.letter_darkness)
    if spec.letters == SOLID:
        solid_weight = spec.solid_weight if spec.solid_layers == "double" else 0.0
        if solid_weight <= 0:
            return f'fill="{colour}" fill-rule="nonzero" stroke="none"'
        return (
            f'fill="{colour}" fill-rule="nonzero" stroke="{colour}" '
            f'stroke-width="{_num(solid_weight / scale)}" '
            f'stroke-linecap="round" stroke-linejoin="round"'
        )
    attrs = [
        'fill="none"',
        f'stroke="{colour}"',
        f'stroke-width="{_num(spec.letter_thickness / scale)}"',
        'stroke-linecap="round"',
        'stroke-linejoin="round"',
    ]
    if spec.letters == DASHED:
        period = dash_period / scale
        if spec.trace_layers == "double":
            # Two short dashes per cycle. The intra-pair gap scales with the
            # line thickness so the rounded caps don't merge at print size.
            small_frac = min(0.85, max(0.3, (spec.letter_thickness + 0.2) / dash_period))
            mark_frac = (2.0 - 1.0 - small_frac) / 2.0
            attrs.append(
                f'stroke-dasharray="{_num(mark_frac * period)} {_num(small_frac * period)} '
                f'{_num(mark_frac * period)} {_num(1.0 * period)}"'
            )
        else:
            dash = _num(period)
            attrs.append(f'stroke-dasharray="{dash} {dash}"')
    elif spec.letters == DOTTED:
        gap = dot_period / scale
        # Zero-length dash + round cap = a dot, the same trick the PDF uses.
        if spec.trace_layers == "double":
            micro_pt = min(
                max(dot_period * 0.45, spec.letter_thickness + 0.1),
                max(0.0, dot_period - spec.letter_thickness - 0.1),
            )
            micro = (micro_pt / dot_period) * gap
            attrs.append(f'stroke-dasharray="0 {_num(micro)} 0 {_num(gap - micro)}"')
        else:
            attrs.append(f'stroke-dasharray="0 {_num(gap)}"')
    return " ".join(attrs)


def _guide_dash_attr(style: str, dash: str, dot: str) -> str:
    if style == LINE_DASHED:
        return f' stroke-dasharray="{dash} {dash}"'
    if style == LINE_DOTTED:
        return f' stroke-dasharray="0 {dot}" stroke-linecap="round"'
    return ""


def rows_svg(
    spec: WorksheetSpec,
    *,
    text: str | None = None,
    rows: int = 1,
    width_pt: float = 200.0,
) -> str:
    """Render ``rows`` writing lines exactly as the PDF would draw them."""
    font = load_font(spec.font_path)
    metrics = compute_metrics(font, spec.lang, spec.line_height_pt)
    pitch = row_pitch(metrics, spec.line_spacing, spec.line_height_pt)
    dash_period, dot_period = trace_periods(spec.line_height_pt, spec.trace_spacing)

    content = text if text is not None else spec.cased_text()
    built = build_rows(
        content,
        font,
        metrics.scale,
        width_pt - TEXT_INSET,
        rows_per_block=rows,
        following_lines=spec.following_lines,
    )[:rows]
    if not built:
        built = []

    height = pitch * max(0, len(built) - 1) + metrics.height + 2 * VERTICAL_PAD
    guide_colour = _rgb(spec.guide_darkness)
    dash = _num(guide_dash(metrics))
    dot = _num(guide_dot(metrics))
    style_attrs = _letter_style_attrs(spec, metrics.scale, dash_period, dot_period)

    defs: dict[int, str] = {}
    body: list[str] = []

    for index, row in enumerate(built):
        baseline = VERTICAL_PAD + metrics.ascent + index * pitch
        for offset, line_style in guide_offsets(
            spec.lang, metrics, guide_style=spec.guide_style, **spec.guide_flags()
        ):
            y = _num(baseline - offset)
            dash_attr = _guide_dash_attr(line_style, dash, dot)
            body.append(
                f'<line x1="0" y1="{y}" x2="{_num(width_pt)}" y2="{y}" '
                f'stroke="{guide_colour}" '
                f'stroke-width="{_num(spec.guide_thickness)}"{dash_attr}/>'
            )
        if not row.text:
            continue

        glyphs, _ = shape(font, row.text)
        placed = []
        for glyph in glyphs:
            path = glyph_path_d(font, glyph.gid)
            if not path:
                continue
            defs.setdefault(glyph.gid, path)
            placed.append(
                f'<use href="#g{glyph.gid}" x="{_num(glyph.x)}" y="{_num(glyph.y)}"/>'
            )
        if placed:
            body.append(
                f'<g transform="translate({_num(TEXT_INSET)} {_num(baseline)}) '
                f'scale({metrics.scale} {-metrics.scale})" {style_attrs}>'
                + "".join(placed)
                + "</g>"
            )

    defs_markup = "".join(f'<path id="g{gid}" d="{d}"/>' for gid, d in defs.items())
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {_num(width_pt)} {_num(height)}" '
        f'width="{_num(width_pt)}" height="{_num(height)}" '
        f'role="img" aria-label="Worksheet sample">'
        f"<defs>{defs_markup}</defs>"
        f'<rect width="100%" height="100%" fill="#fff"/>'
        f"{''.join(body)}"
        f"</svg>"
    )
