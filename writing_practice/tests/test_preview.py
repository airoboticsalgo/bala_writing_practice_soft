"""The SVG option samples must show what the PDF will actually print."""

import re
from xml.etree import ElementTree

from reportlab.lib.units import mm

from app.render.guides import compute_metrics, guide_offsets, row_pitch
from app.render.preview import VERTICAL_PAD, rows_svg
from app.render.shaper import shape
from app.render.spec import WorksheetSpec

from .conftest import ENGLISH_FONT, HINDI_FONT

SVG = "{http://www.w3.org/2000/svg}"


def english(**overrides) -> WorksheetSpec:
    base = {
        "lang": "english",
        "font_path": ENGLISH_FONT,
        "text": "adg",
        "top_line": True,
        "mid_line": True,
        "descender_line": False,
    }
    base.update(overrides)
    return WorksheetSpec(**base)


def parse(svg: str):
    return ElementTree.fromstring(svg)


def glyph_group(root):
    return root.find(f".//{SVG}g")


def test_svg_is_well_formed_and_sized():
    root = parse(rows_svg(english(), rows=1, width_pt=210))
    assert root.tag == f"{SVG}svg"
    assert root.get("viewBox").startswith("0 0 210 ")


def test_every_use_resolves_to_a_defined_path():
    root = parse(rows_svg(english(text="the quick brown"), rows=1, width_pt=400))
    defined = {path.get("id") for path in root.iter(f"{SVG}path")}
    used = {use.get("href").lstrip("#") for use in root.iter(f"{SVG}use")}
    assert used
    assert used <= defined


def test_glyphs_are_defined_once_and_reused():
    """`aaaa` must define one path and use it four times."""
    root = parse(rows_svg(english(text="aaaa"), rows=1, width_pt=300))
    assert len(list(root.iter(f"{SVG}path"))) == 1
    assert len(list(root.iter(f"{SVG}use"))) == 4


def test_solid_letters_are_filled_with_non_zero_winding():
    group = glyph_group(parse(rows_svg(english(letters="solid"))))
    assert group.get("fill") not in (None, "none")
    assert group.get("fill-rule") == "nonzero"
    assert group.get("stroke") == "none"


def test_outlined_letters_are_stroked_not_filled():
    group = glyph_group(parse(rows_svg(english(letters="outlined"))))
    assert group.get("fill") == "none"
    assert group.get("stroke") not in (None, "none")
    assert group.get("stroke-dasharray") is None


def test_dashed_letters_carry_a_dash_pattern():
    group = glyph_group(parse(rows_svg(english(letters="dashed"))))
    assert group.get("fill") == "none"
    assert group.get("stroke-dasharray")


def test_dotted_letters_carry_a_zero_length_dash_and_a_round_cap():
    group = glyph_group(parse(rows_svg(english(letters="dotted"))))
    assert group.get("fill") == "none"
    assert group.get("stroke-dasharray").startswith("0 ")
    assert group.get("stroke-linecap") == "round"


def test_trace_spacing_widens_the_dot_period():
    def period(spacing):
        group = glyph_group(
            parse(rows_svg(english(letters="dotted", trace_spacing=spacing)))
        )
        return float(group.get("stroke-dasharray").split()[1])

    assert period("tight") < period("normal") < period("wide")


def test_single_layer_solid_has_no_stroke():
    plain = glyph_group(parse(rows_svg(english(letters="solid"))))
    assert plain.get("stroke") == "none"


def test_double_layer_solid_strokes_with_the_weight(english_font):
    scale = compute_metrics(english_font, "english", 12 * mm).scale
    heavy = glyph_group(
        parse(rows_svg(english(letters="solid", solid_layers="double", solid_weight=0.8)))
    )
    assert heavy.get("stroke") == heavy.get("fill")
    assert abs(float(heavy.get("stroke-width")) * scale - 0.8) < 0.01


def test_stroke_width_survives_the_scale_transform(english_font):
    """The glyph group is scaled, so stroke-width must be pre-divided by it."""
    scale = compute_metrics(english_font, "english", 12 * mm).scale
    for thickness in (0.4, 1.6):
        group = glyph_group(
            parse(rows_svg(english(letters="outlined", letter_thickness=thickness)))
        )
        assert abs(float(group.get("stroke-width")) * scale - thickness) < 0.01


def test_darkness_changes_the_letter_colour():
    faint = glyph_group(parse(rows_svg(english(letters="solid", letter_darkness=10))))
    black = glyph_group(parse(rows_svg(english(letters="solid", letter_darkness=100))))
    assert black.get("fill") == "rgb(0,0,0)"
    assert faint.get("fill") != black.get("fill")


def guide_ys(root):
    return [round(float(line.get("y1")), 2) for line in root.iter(f"{SVG}line")]


def test_base_line_is_always_drawn():
    root = parse(rows_svg(english(top_line=False, mid_line=False, descender_line=False)))
    assert len(guide_ys(root)) == 1


def test_guide_lines_match_the_pdf_metrics(english_font):
    spec = english(top_line=True, mid_line=True, descender_line=True)
    metrics = compute_metrics(english_font, "english", spec.line_height_pt)
    root = parse(rows_svg(spec))

    offsets = guide_offsets("english", metrics, **spec.guide_flags())
    assert len(guide_ys(root)) == len(offsets) == 4

    # SVG y grows downwards, so a guide above the base line has a smaller y --
    # and the descender guide is *below* the base line, hence the largest y.
    baseline = VERTICAL_PAD + metrics.ascent
    expected = sorted(round(baseline - offset, 2) for offset, _ in offsets)
    assert sorted(guide_ys(root)) == expected
    assert round(baseline, 2) in guide_ys(root)
    assert max(guide_ys(root)) > baseline  # the descender line


def test_only_the_mid_line_is_dashed_for_english():
    root = parse(rows_svg(english(top_line=True, mid_line=True)))
    dashed = [line for line in root.iter(f"{SVG}line") if line.get("stroke-dasharray")]
    assert len(dashed) == 1


def test_guide_style_applies_to_every_line_including_the_base_line():
    def patterns(style):
        root = parse(rows_svg(english(top_line=True, mid_line=True, guide_style=style)))
        return [line.get("stroke-dasharray") for line in root.iter(f"{SVG}line")]

    assert patterns("solid") == [None, None, None]
    assert all(p and not p.startswith("0 ") for p in patterns("dashed"))
    assert all(p and p.startswith("0 ") for p in patterns("dotted"))


def test_row_spacing_matches_the_pdf_pitch(english_font):
    for spacing in ("single", "double"):
        spec = english(line_spacing=spacing)
        metrics = compute_metrics(english_font, "english", spec.line_height_pt)
        pitch = row_pitch(metrics, spacing, spec.line_height_pt)
        root = parse(rows_svg(spec, rows=2, width_pt=210))
        baselines = sorted(set(guide_ys(root)))
        # Two rows of identical guide sets: the offset between them is the pitch.
        assert any(abs((b - baselines[0]) - pitch) < 0.05 for b in baselines)


def test_following_lines_blank_leaves_the_second_row_empty():
    repeat = parse(rows_svg(english(following_lines="repeat"), rows=2, width_pt=210))
    blank = parse(rows_svg(english(following_lines="blank"), rows=2, width_pt=210))
    assert len(list(repeat.iter(f"{SVG}g"))) == 2
    assert len(list(blank.iter(f"{SVG}g"))) == 1


def test_hindi_sample_is_shaped_in_the_same_order_as_the_pdf(hindi_font):
    spec = WorksheetSpec(lang="hindi", font_path=HINDI_FONT, text="कि कु")
    root = parse(rows_svg(spec, rows=1, width_pt=300))
    used = [int(use.get("href").lstrip("#g")) for use in root.iter(f"{SVG}use")]
    glyphs, _ = shape(hindi_font, "कि कु")
    expected = [g.gid for g in glyphs if g.gid in used]
    assert used == expected
    # The i-matra is reordered ahead of its consonant, as in the PDF.
    consonant = hindi_font.glyph_order.index(hindi_font.cmap[ord("क")])
    assert used.index(consonant) == 1


def test_empty_text_still_renders_the_guides():
    root = parse(rows_svg(english(text="x"), text="", rows=2, width_pt=210))
    assert guide_ys(root)
    assert not list(root.iter(f"{SVG}use"))


# --- the HTTP endpoint -------------------------------------------------------


def test_sample_endpoint_returns_svg(client):
    response = client.get(
        "/english/writing/handwriting/print-practice/sample.svg?letters=dashed&rows=2"
    )
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.get_data(as_text=True).startswith("<svg")


def test_sample_endpoint_needs_no_text(client):
    response = client.get("/hindi/writing/handwriting/print-practice/sample.svg")
    assert response.status_code == 200
    assert "<use" in response.get_data(as_text=True)


def test_sample_endpoint_survives_garbage_input(client):
    """A sample is decoration: bad query values must degrade, never 500."""
    response = client.get(
        "/english/writing/handwriting/print-practice/sample.svg"
        "?rows=abc&w=-99999&line_height_mm=nope&letters=sparkly&letter_thickness=x"
    )
    assert response.status_code == 200
    assert response.get_data(as_text=True).startswith("<svg")


def test_sample_endpoint_clamps_the_requested_width(client):
    response = client.get(
        "/english/writing/handwriting/print-practice/sample.svg?w=100000"
    )
    width = float(re.search(r'width="([\d.]+)"', response.get_data(as_text=True)).group(1))
    assert width <= 900


def test_form_pages_include_a_sample_for_every_choice(client):
    for lang in ("english", "hindi"):
        body = client.get(f"/{lang}/writing/handwriting/print-practice").get_data(
            as_text=True
        )
        # 4 letter styles + 3 guide lines + 5 guide styles + 2 spacings
        # + 2 following-line modes
        assert body.count('class="sample"') == 16
        assert 'id="live-preview"' in body
        assert "sample.svg" in body
