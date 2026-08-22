import pytest

from app.render import spec as spec_lib
from app.render.spec import SpecError, from_form


def test_empty_text_is_rejected(settings):
    with pytest.raises(SpecError) as excinfo:
        from_form({"text": "   \n  "}, "english", settings)
    assert "type some text" in excinfo.value.errors[0]


def test_over_limit_text_is_rejected(settings):
    limit = settings.int("worksheet", "max_text_chars")
    with pytest.raises(SpecError) as excinfo:
        from_form({"text": "a" * (limit + 1)}, "english", settings)
    assert "limit" in excinfo.value.errors[0]


def test_at_limit_text_is_accepted(settings):
    limit = settings.int("worksheet", "max_text_chars")
    spec = from_form({"text": "a" * limit}, "english", settings)
    assert len(spec.text) == limit


def test_unknown_language_is_rejected(settings):
    with pytest.raises(SpecError):
        from_form({"text": "cat"}, "klingon", settings)


def test_garbage_numbers_are_clamped_to_allowed_values(settings):
    spec = from_form(
        {
            "text": "cat",
            "line_height_mm": "999",
            "guide_thickness": "banana",
            "letter_thickness": "-4",
            "guide_darkness": "500",
            "letter_darkness": "-20",
            "rows_per_block": "99",
            "letters": "sparkly",
            "solid_layers": "triple",
            "solid_weight": "99",
            "trace_spacing": "enormous",
            "guide_style": "squiggly",
            "paper_size": "A0",
            "orientation": "sideways",
        },
        "english",
        settings,
    )
    assert spec.line_height_mm == max(spec_lib.LINE_HEIGHTS_MM)
    assert spec.guide_thickness in spec_lib.GUIDE_THICKNESSES
    assert spec.letter_thickness == min(spec_lib.LETTER_THICKNESSES)
    assert spec.guide_darkness == 100.0
    assert spec.letter_darkness == 0.0
    assert spec.rows_per_block == max(spec_lib.ROWS_PER_BLOCK)
    assert spec.letters in spec_lib.LETTER_STYLES
    assert spec.solid_layers == "single"
    assert spec.solid_weight == max(spec_lib.SOLID_WEIGHTS)
    assert spec.trace_spacing == "normal"
    assert spec.guide_style == "classic"
    assert spec.paper_size == "A4"
    assert spec.orientation == "tall"


def test_checkboxes_absent_means_unchecked(settings):
    spec = from_form({"text": "cat"}, "english", settings)
    assert spec.top_line is False
    assert spec.mid_line is False
    spec = from_form({"text": "cat", "top_line": "on"}, "english", settings)
    assert spec.top_line is True


def test_case_transform(settings):
    spec = from_form({"text": "don't stop\nnow", "case": "Title Case"}, "english", settings)
    assert spec.cased_text() == "Don't Stop\nNow"
    spec = from_form({"text": "AbC", "case": "lowercase"}, "english", settings)
    assert spec.cased_text() == "abc"


def test_orientation_swaps_page_dimensions(settings):
    tall = from_form({"text": "a"}, "english", settings)
    wide = from_form({"text": "a", "orientation": "wide"}, "english", settings)
    assert tall.page_size == (wide.page_size[1], wide.page_size[0])
    assert wide.page_size[0] > wide.page_size[1]


def test_hindi_gets_a_devanagari_font(settings):
    spec = from_form({"text": "क"}, "hindi", settings)
    assert "Devanagari" in spec.font_file or "Mukta" in spec.font_file


def test_bogus_font_falls_back_to_the_language_default(settings):
    spec = from_form({"text": "cat", "font_file": "Comic Sans.ttf"}, "english", settings)
    assert spec.font_file == settings.get("fonts", "english_default")


def test_hindi_cannot_borrow_a_latin_only_font(settings):
    spec = from_form({"text": "क", "font_file": "ABeeZee-Regular.ttf"}, "hindi", settings)
    assert spec.font_file != "ABeeZee-Regular.ttf"


def test_form_values_round_trip_every_choice(settings):
    submitted = {
        "text": "cat",
        "page_title": "My Sheet",
        "instructions": "Trace it",
        "line_height_mm": "20",
        "letters": "dotted",
        "letter_thickness": "1.2",
        "solid_layers": "double",
        "solid_weight": "0.4",
        "trace_spacing": "wide",
        "guide_thickness": "1.0",
        "guide_style": "dotted",
        "line_spacing": "double",
        "following_lines": "blank",
        "rows_per_block": "5",
        "paper_size": "Letter",
        "orientation": "wide",
        "mid_line": "on",
    }
    values = spec_lib.form_values(submitted, "english", settings)
    assert values["page_title"] == "My Sheet"
    assert values["line_height_mm"] == 20
    assert values["letters"] == "dotted"
    assert values["letter_thickness"] == 1.2
    assert values["solid_layers"] == "double"
    assert values["solid_weight"] == 0.4
    assert values["trace_spacing"] == "wide"
    assert values["guide_style"] == "dotted"
    assert values["line_spacing"] == "double"
    assert values["following_lines"] == "blank"
    assert values["rows_per_block"] == 5
    assert values["paper_size"] == "Letter"
    assert values["orientation"] == "wide"
    assert values["mid_line"] is True
    assert values["top_line"] is False
