"""Page assembly: header, writing rows, footer, pagination."""

from __future__ import annotations

from io import BytesIO

from reportlab import rl_config
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

# Page streams are already Flate-compressed; layering ASCII85 on top costs more
# time than everything else in this module put together (reportlab's base85
# encoder is pure Python here) and makes the file bigger. Binary streams are
# perfectly valid PDF.
rl_config.useA85 = 0

from .fonts import load_font
from .guides import compute_metrics, draw_row_guides, row_pitch
from .layout import build_rows, paginate, rows_per_page
from .paint import SOLID, GlyphPainter, draw_text, text_width, trace_periods
from .spec import WorksheetSpec

TITLE_SIZE = 16.0
INSTRUCTIONS_SIZE = 9.5
NAME_SIZE = 10.0
FOOTER_SIZE = 7.0
MARGIN_MM_DEFAULT = 12.0


def _header_height(spec: WorksheetSpec) -> float:
    height = 0.0
    if spec.page_title:
        height += TITLE_SIZE * 1.6
    if spec.instructions:
        height += INSTRUCTIONS_SIZE * 1.8
    if spec.child_name or spec.show_date_line:
        height += NAME_SIZE * 2.4
    return height


def _draw_header(canvas, spec, font, page_width, top_y, margin) -> None:
    y = top_y
    if spec.page_title:
        scale = TITLE_SIZE / font.upem
        width = text_width(font, spec.page_title, scale)
        y -= TITLE_SIZE
        draw_text(
            canvas,
            font,
            spec.page_title,
            (page_width - width) / 2.0,
            y,
            scale,
            style=SOLID,
            darkness=100.0,
        )
        y -= TITLE_SIZE * 0.6

    if spec.instructions:
        scale = INSTRUCTIONS_SIZE / font.upem
        width = text_width(font, spec.instructions, scale)
        y -= INSTRUCTIONS_SIZE
        draw_text(
            canvas,
            font,
            spec.instructions,
            (page_width - width) / 2.0,
            y,
            scale,
            style=SOLID,
            darkness=55.0,
        )
        y -= INSTRUCTIONS_SIZE * 0.8

    if spec.child_name or spec.show_date_line:
        scale = NAME_SIZE / font.upem
        y -= NAME_SIZE
        left = f"Name: {spec.child_name}" if spec.child_name else "Name:"
        draw_text(canvas, font, left, margin, y, scale, style=SOLID, darkness=70.0)
        left_width = text_width(font, left, scale)
        canvas.saveState()
        canvas.setStrokeGray(0.45)
        canvas.setLineWidth(0.5)
        rule_end = page_width / 2.0 - 10.0
        if not spec.child_name:
            canvas.line(margin + left_width + 4, y - 1.5, rule_end, y - 1.5)
        if spec.show_date_line:
            date_x = page_width / 2.0 + 10.0
            draw_text(canvas, font, "Date:", date_x, y, scale, style=SOLID, darkness=70.0)
            date_width = text_width(font, "Date:", scale)
            canvas.line(
                date_x + date_width + 4, y - 1.5, page_width - margin, y - 1.5
            )
        canvas.restoreState()


def render_worksheet(spec: WorksheetSpec, margin_mm: float = MARGIN_MM_DEFAULT) -> bytes:
    """Render ``spec`` to PDF bytes."""
    font = load_font(spec.font_path)
    page_width, page_height = spec.page_size
    margin = margin_mm * mm

    metrics = compute_metrics(font, spec.lang, spec.line_height_pt)
    pitch = row_pitch(metrics, spec.line_spacing, spec.line_height_pt)

    content_width = page_width - 2 * margin
    header = _header_height(spec)
    content_top = page_height - margin - header
    footer_room = FOOTER_SIZE * 2.5
    available = content_top - margin - footer_room

    rows = build_rows(
        spec.cased_text(),
        font,
        metrics.scale,
        content_width,
        rows_per_block=spec.rows_per_block,
        following_lines=spec.following_lines,
    )
    per_page = rows_per_page(available, pitch, metrics.height)
    pages = paginate(rows, per_page)

    buffer = BytesIO()
    canvas = pdfcanvas.Canvas(buffer, pagesize=(page_width, page_height))
    canvas.setTitle(spec.page_title or "Handwriting Practice")

    dash_period, dot_period = trace_periods(spec.line_height_pt, spec.trace_spacing)
    solid_weight = spec.solid_weight if spec.solid_layers == "double" else 0.0
    painter = GlyphPainter(
        font,
        metrics.scale,
        style=spec.letters,
        darkness=spec.letter_darkness,
        thickness=spec.letter_thickness,
        dash_period=dash_period,
        dot_period=dot_period,
        weight=solid_weight,
        trace_layers=spec.trace_layers,
    )

    for index, page_rows in enumerate(pages, start=1):
        _draw_header(canvas, spec, font, page_width, page_height - margin, margin)

        for row_index, row in enumerate(page_rows):
            baseline = content_top - row_index * pitch - metrics.ascent
            draw_row_guides(
                canvas,
                lang=spec.lang,
                metrics=metrics,
                x0=margin,
                x1=page_width - margin,
                baseline_y=baseline,
                darkness=spec.guide_darkness,
                thickness=spec.guide_thickness,
                guide_style=spec.guide_style,
                **spec.guide_flags(),
            )
            if row.text:
                painter.draw(canvas, row.text, margin + 2.0, baseline)

        canvas.setFont("Helvetica", FOOTER_SIZE)
        canvas.setFillGray(0.5)
        canvas.drawCentredString(
            page_width / 2.0, margin * 0.55, f"Page {index} of {len(pages)}"
        )
        canvas.showPage()

    painter.finalize(canvas)
    canvas.save()
    return buffer.getvalue()
