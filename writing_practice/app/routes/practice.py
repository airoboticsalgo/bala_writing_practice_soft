"""Pages 2 and 3: the English and Hindi worksheet builders."""

from __future__ import annotations

import re
from datetime import datetime

from flask import Blueprint, Response, current_app, render_template, request, url_for

from ..data import PRESETS
from ..render import spec as spec_lib
from ..render.fonts import fonts_for_language
from ..render.page import render_worksheet
from ..render.preview import rows_svg

bp = Blueprint("practice", __name__)

ROUTE = "/<any(english,hindi):lang>/writing/handwriting/print-practice"

LANG_LABELS = {
    "english": {"name": "English", "native": "English", "dir": "ltr"},
    "hindi": {"name": "Hindi", "native": "हिंदी", "dir": "ltr"},
}

#: Text used by option thumbnails, chosen to exercise the guide lines:
#: ascenders, descenders and x-height for English; matras above and below for Hindi.
SAMPLE_TEXT = {"english": "adg", "hindi": "कि कु"}

#: Widest sample a browser may request, in points, so a stray query can't ask for
#: a metre-wide SVG.
MAX_SAMPLE_WIDTH = 900.0
MAX_SAMPLE_ROWS = 20
MAX_SAMPLE_CHARS = 300


def _settings():
    return current_app.config["SETTINGS"]


def _sample_url(lang: str, values: dict, overrides: dict) -> str:
    """Build a sample.svg URL from the current form values plus overrides.

    Unchecked boxes must be absent rather than ``False``, since that is how the
    form itself encodes them.
    """
    params: dict[str, object] = {}
    for key, value in {**values, **overrides}.items():
        if key == "lang" or value is None or value == "":
            continue
        if isinstance(value, bool):
            if value:
                params[key] = "on"
        elif key == "text":
            # A sample only ever shows the first line or two; keep the URL sane.
            params[key] = str(value)[:MAX_SAMPLE_CHARS]
        else:
            params[key] = value
    return url_for("practice.sample", lang=lang, **params)


def _context(lang: str, values: dict, errors: list[str] | None = None) -> dict:
    settings = _settings()
    return {
        "lang": lang,
        "labels": LANG_LABELS[lang],
        "v": values,
        "errors": errors or [],
        "sample_text": SAMPLE_TEXT[lang],
        "sample_url": lambda **overrides: _sample_url(lang, values, overrides),
        "presets": PRESETS[lang],
        "fonts": fonts_for_language(settings.path("fonts", "fonts_dir"), lang),
        "options": {
            "line_heights": spec_lib.LINE_HEIGHTS_MM,
            "guide_thicknesses": spec_lib.GUIDE_THICKNESSES,
            "guide_styles": spec_lib.GUIDE_STYLES,
            "letter_thicknesses": spec_lib.LETTER_THICKNESSES,
            "letter_styles": spec_lib.LETTER_STYLES,
            "solid_layers": spec_lib.SOLID_LAYERS,
            "solid_weights": spec_lib.SOLID_WEIGHTS,
            "trace_layers": spec_lib.TRACE_LAYERS,
            "trace_spacings": spec_lib.TRACE_SPACINGS,
            "line_spacings": spec_lib.LINE_SPACINGS,
            "following_lines": spec_lib.FOLLOWING_LINES,
            "paper_sizes": spec_lib.PAPER_SIZES,
            "orientations": spec_lib.ORIENTATIONS,
            "cases": spec_lib.CASES,
            "rows_per_block": spec_lib.ROWS_PER_BLOCK,
        },
        "max_chars": settings.int("worksheet", "max_text_chars"),
    }


def _file_name(title: str, lang: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or lang
    return f"{slug}-{datetime.now():%Y%m%d-%H%M%S}.pdf"


@bp.get(ROUTE)
def form(lang: str):
    return render_template(
        "worksheet_form.html", **_context(lang, spec_lib.defaults(lang, _settings()))
    )


def _clamped(raw, low, high, default):
    try:
        return max(low, min(high, type(default)(float(raw))))
    except (TypeError, ValueError):
        return default


@bp.get(f"{ROUTE}/sample.svg")
def sample(lang: str):
    """A live sample of one or more writing rows for the given options.

    Used both for the little thumbnail beside each choice and for the big preview
    of the user's own text. Never fails on bad input: a sample is decoration, so
    fall back to the defaults rather than showing the user an error.
    """
    args = request.args.to_dict()
    text = args.get("text", "").strip()
    if not text:
        text = SAMPLE_TEXT[lang]
    args["text"] = text[:MAX_SAMPLE_CHARS]

    try:
        spec = spec_lib.from_form(args, lang, _settings())
    except spec_lib.SpecError:
        spec = spec_lib.from_form({"text": SAMPLE_TEXT[lang]}, lang, _settings())

    svg = rows_svg(
        spec,
        text=spec.cased_text(),
        rows=_clamped(args.get("rows"), 1, MAX_SAMPLE_ROWS, 1),
        width_pt=_clamped(args.get("w"), 60.0, MAX_SAMPLE_WIDTH, 200.0),
    )
    return Response(
        svg,
        mimetype="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300"},
    )


@bp.post(f"{ROUTE}/generate")
def generate(lang: str):
    settings = _settings()
    try:
        spec = spec_lib.from_form(request.form, lang, settings)
    except spec_lib.SpecError as error:
        context = _context(
            lang, spec_lib.form_values(request.form, lang, settings), error.errors
        )
        return render_template("worksheet_form.html", **context), 400

    pdf = render_worksheet(spec, margin_mm=settings.float("worksheet", "margin_mm"))
    name = _file_name(spec.page_title, lang)

    if settings.bool("output", "save_generated"):
        out_dir = settings.path("output", "output_dir")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / name).write_bytes(pdf)

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{name}"'},
    )
