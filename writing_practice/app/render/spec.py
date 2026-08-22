"""The worksheet request object.

``WorksheetSpec`` is the only thing the renderer sees -- it never touches
``request``, ``session`` or any Flask global, so it stays unit-testable and
callable from a plain script.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.units import mm

from .fonts import resolve_font
from .guides import CLASSIC, GUIDE_STYLES
from .paint import DASHED, LETTER_STYLES, SPACING_FACTORS

LANGUAGES = ("english", "hindi")
LINE_HEIGHTS_MM = (8, 10, 12, 15, 20, 25)
GUIDE_THICKNESSES = (0.15, 0.25, 0.4, 0.5, 0.75, 1.0, 1.5, 2.0)
LETTER_THICKNESSES = (0.2, 0.3, 0.4, 0.6, 0.8, 1.0, 1.2, 1.6, 2.0, 2.5)
#: Extra stroke laid over a solid letter. 0 means "just fill it", the historical
#: behaviour and the only value that keeps a solid letter its true outline width.
SOLID_WEIGHTS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.2)
SOLID_LAYERS = ("single", "double")
TRACE_LAYERS: tuple[str, ...] = ("single",)
TRACE_SPACINGS = tuple(SPACING_FACTORS)
LINE_SPACINGS = ("single", "double")
FOLLOWING_LINES = ("repeat", "blank")
PAPER_SIZES = ("A4", "Letter")
ORIENTATIONS = ("tall", "wide")
CASES = ("as-typed", "UPPERCASE", "lowercase", "Title Case")
ROWS_PER_BLOCK = tuple(range(1, 21))

_PAGE_SIZES = {"A4": A4, "Letter": LETTER}


class SpecError(ValueError):
    """Raised for user-fixable input problems; carries every message at once."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class WorksheetSpec:
    lang: str
    font_path: Path
    text: str
    page_title: str = "Handwriting Practice"
    instructions: str = ""
    case: str = "as-typed"
    child_name: str = ""
    show_date_line: bool = False

    line_height_mm: float = 12.0
    guide_darkness: float = 30.0
    guide_thickness: float = 0.5
    guide_style: str = CLASSIC
    top_line: bool = True
    mid_line: bool = True
    descender_line: bool = False
    shiro_rekha: bool = True
    upper_matra_line: bool = True
    lower_matra_line: bool = False

    letters: str = DASHED
    letter_darkness: float = 50.0
    letter_thickness: float = 0.6
    solid_layers: str = "single"
    solid_weight: float = 0.0
    trace_layers: str = "single"
    trace_spacing: str = "normal"

    line_spacing: str = "single"
    following_lines: str = "repeat"
    rows_per_block: int = 3

    paper_size: str = "A4"
    orientation: str = "tall"

    @property
    def line_height_pt(self) -> float:
        return self.line_height_mm * mm

    @property
    def page_size(self) -> tuple[float, float]:
        width, height = _PAGE_SIZES[self.paper_size]
        return (height, width) if self.orientation == "wide" else (width, height)

    @property
    def font_file(self) -> str:
        return self.font_path.name

    def guide_flags(self) -> dict[str, bool]:
        return {
            "top_line": self.top_line,
            "mid_line": self.mid_line,
            "descender_line": self.descender_line,
            "shiro_rekha": self.shiro_rekha,
            "upper_matra_line": self.upper_matra_line,
            "lower_matra_line": self.lower_matra_line,
        }

    def cased_text(self) -> str:
        lines = self.text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return "\n".join(_apply_case(line, self.case) for line in lines)

    def to_form_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["font_path"] = None
        data["font_file"] = self.font_file
        return data


def _apply_case(line: str, case: str) -> str:
    if case == "UPPERCASE":
        return line.upper()
    if case == "lowercase":
        return line.lower()
    if case == "Title Case":
        # str.title() mangles apostrophes ("don't" -> "Don'T"), so do it by word.
        return " ".join(w[:1].upper() + w[1:] if w else w for w in line.split(" "))
    return line


def _choice(value: Any, allowed: tuple, default: Any) -> Any:
    return value if value in allowed else default


def _nearest(value: Any, allowed: tuple[float, ...], default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(allowed, key=lambda option: abs(option - number))


def _percent(value: Any, default: float) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return default


def _checked(form: Mapping[str, Any], key: str) -> bool:
    return form.get(key) is not None


def defaults(lang: str, settings) -> dict[str, Any]:
    """Initial form values for a GET, straight from config/app.conf."""
    return {
        "lang": lang,
        "page_title": settings.get("worksheet", "page_title"),
        "instructions": "",
        "text": "",
        "case": "as-typed",
        "child_name": "",
        "show_date_line": False,
        "font_file": settings.get("fonts", f"{lang}_default"),
        "line_height_mm": _nearest(
            settings.float("worksheet", "line_height_mm"), LINE_HEIGHTS_MM, 12.0
        ),
        "guide_darkness": settings.float("guides", "darkness"),
        "guide_thickness": _nearest(
            settings.float("guides", "thickness"), GUIDE_THICKNESSES, 0.5
        ),
        "guide_style": _choice(settings.get("guides", "style"), GUIDE_STYLES, CLASSIC),
        "top_line": settings.bool("guides", "english_top_line"),
        "mid_line": settings.bool("guides", "english_mid_line"),
        "descender_line": settings.bool("guides", "english_descender_line"),
        "shiro_rekha": settings.bool("guides", "hindi_shiro_rekha"),
        "upper_matra_line": settings.bool("guides", "hindi_upper_matra_line"),
        "lower_matra_line": settings.bool("guides", "hindi_lower_matra_line"),
        "letters": _choice(settings.get("letters", "style"), LETTER_STYLES, DASHED),
        "letter_darkness": settings.float("letters", "darkness"),
        "letter_thickness": _nearest(
            settings.float("letters", "thickness"), LETTER_THICKNESSES, 0.6
        ),
        "solid_layers": _choice(
            settings.get("letters", "solid_layers"), SOLID_LAYERS, "single"
        ),
        "solid_weight": _nearest(
            settings.float("letters", "solid_weight"), SOLID_WEIGHTS, 0.0
        ),
        "trace_layers": _choice(
            settings.get("letters", "trace_layers"), TRACE_LAYERS, "single"
        ),
        "trace_spacing": _choice(
            settings.get("letters", "trace_spacing"), TRACE_SPACINGS, "normal"
        ),
        "line_spacing": _choice(
            settings.get("worksheet", "line_spacing"), LINE_SPACINGS, "single"
        ),
        "following_lines": _choice(
            settings.get("worksheet", "following_lines"), FOLLOWING_LINES, "repeat"
        ),
        "rows_per_block": int(
            _nearest(settings.int("worksheet", "rows_per_block"), ROWS_PER_BLOCK, 3)
        ),
        "paper_size": _choice(settings.get("worksheet", "paper_size"), PAPER_SIZES, "A4"),
        "orientation": _choice(
            settings.get("worksheet", "orientation"), ORIENTATIONS, "tall"
        ),
    }


def form_values(form: Mapping[str, Any], lang: str, settings) -> dict[str, Any]:
    """Clamp a POSTed form to valid values without validating the text.

    The form template renders from this, so a rejected submission comes back
    with every choice the user made still selected.
    """
    base = defaults(lang, settings)
    return {
        **base,
        "text": str(form.get("text", "")).replace("\r\n", "\n").replace("\r", "\n"),
        "font_file": str(form.get("font_file") or base["font_file"]),
        "page_title": str(form.get("page_title", base["page_title"])).strip()[:120],
        "instructions": str(form.get("instructions", "")).strip()[:200],
        "case": _choice(form.get("case"), CASES, "as-typed"),
        "child_name": str(form.get("child_name", "")).strip()[:60],
        "show_date_line": _checked(form, "show_date_line"),
        "line_height_mm": _nearest(
            form.get("line_height_mm"), LINE_HEIGHTS_MM, base["line_height_mm"]
        ),
        "guide_darkness": _percent(form.get("guide_darkness"), base["guide_darkness"]),
        "guide_thickness": _nearest(
            form.get("guide_thickness"), GUIDE_THICKNESSES, base["guide_thickness"]
        ),
        "guide_style": _choice(
            form.get("guide_style"), GUIDE_STYLES, base["guide_style"]
        ),
        "top_line": _checked(form, "top_line"),
        "mid_line": _checked(form, "mid_line"),
        "descender_line": _checked(form, "descender_line"),
        "shiro_rekha": _checked(form, "shiro_rekha"),
        "upper_matra_line": _checked(form, "upper_matra_line"),
        "lower_matra_line": _checked(form, "lower_matra_line"),
        "letters": _choice(form.get("letters"), LETTER_STYLES, base["letters"]),
        "letter_darkness": _percent(form.get("letter_darkness"), base["letter_darkness"]),
        "letter_thickness": _nearest(
            form.get("letter_thickness"), LETTER_THICKNESSES, base["letter_thickness"]
        ),
        "solid_layers": _choice(
            form.get("solid_layers"), SOLID_LAYERS, base["solid_layers"]
        ),
        "solid_weight": _nearest(
            form.get("solid_weight"), SOLID_WEIGHTS, base["solid_weight"]
        ),
        "trace_layers": _choice(
            form.get("trace_layers"), TRACE_LAYERS, base["trace_layers"]
        ),
        "trace_spacing": _choice(
            form.get("trace_spacing"), TRACE_SPACINGS, base["trace_spacing"]
        ),
        "line_spacing": _choice(
            form.get("line_spacing"), LINE_SPACINGS, base["line_spacing"]
        ),
        "following_lines": _choice(
            form.get("following_lines"), FOLLOWING_LINES, base["following_lines"]
        ),
        "rows_per_block": int(
            _nearest(form.get("rows_per_block"), ROWS_PER_BLOCK, base["rows_per_block"])
        ),
        "paper_size": _choice(form.get("paper_size"), PAPER_SIZES, base["paper_size"]),
        "orientation": _choice(
            form.get("orientation"), ORIENTATIONS, base["orientation"]
        ),
    }


def from_form(form: Mapping[str, Any], lang: str, settings) -> WorksheetSpec:
    """Validate and clamp a POSTed form. Raises :class:`SpecError`."""
    if lang not in LANGUAGES:
        raise SpecError([f"Unknown language {lang!r}."])

    values = form_values(form, lang, settings)
    max_chars = settings.int("worksheet", "max_text_chars")

    errors: list[str] = []
    if not values["text"].strip():
        errors.append("Please type some text to practise.")
    if len(values["text"]) > max_chars:
        errors.append(
            f"That is {len(values['text']):,} characters; the limit is {max_chars:,}. "
            "Please shorten the text."
        )
    if errors:
        raise SpecError(errors)

    font = resolve_font(
        settings.path("fonts", "fonts_dir"),
        lang,
        values["font_file"],
        settings.get("fonts", f"{lang}_default"),
    )
    values.pop("font_file")
    values.pop("lang")
    return WorksheetSpec(lang=lang, font_path=font.path, **values)
