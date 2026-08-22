import re
import time
from io import BytesIO

from pypdf import PdfReader
from reportlab.lib.units import mm

from app.render.glyphs import glyph_contours
from app.render.guides import compute_metrics
from app.render.page import render_worksheet
from app.render.shaper import shape
from app.render.spec import WorksheetSpec

from .conftest import ENGLISH_FONT, HINDI_FONT


def bare_spec(**overrides) -> WorksheetSpec:
    """A spec with the decorations off, so a content stream shows only letters."""
    base = {
        "lang": "english",
        "font_path": ENGLISH_FONT,
        "text": "cat",
        "page_title": "",
        "instructions": "",
        "top_line": False,
        "mid_line": False,
        "descender_line": False,
        "rows_per_block": 1,
    }
    base.update(overrides)
    return WorksheetSpec(**base)


def content_of(pdf: bytes, page: int = 0) -> bytes:
    """Page stream plus the glyph form streams it references.

    Letters live in Form XObjects, so the paint operators are not in the page
    stream itself; the graphics state (gray, width, dash) is.
    """
    page_obj = PdfReader(BytesIO(pdf)).pages[page]
    parts = [page_obj.get_contents().get_data()]
    parts.extend(form.get_data() for form in glyph_forms(page_obj).values())
    return b"\n".join(parts)


def glyph_forms(page_obj) -> dict:
    xobjects = page_obj.get("/Resources", {}).get("/XObject", {})
    return {name: xobjects[name] for name in xobjects}


def page_count(pdf: bytes) -> int:
    return len(PdfReader(BytesIO(pdf)).pages)


def test_output_is_a_pdf():
    pdf = render_worksheet(bare_spec())
    assert pdf.startswith(b"%PDF-")
    assert page_count(pdf) == 1


# Fill / stroke / dash operators, matched on their own line in the content stream.
FILL_OP = rb"(?m)^f\*?$"
NONZERO_FILL_OP = rb"(?m)^f$"
STROKE_OP = rb"(?m)^S$"
DASH_ARRAY = rb"\[[\d.]+ [\d.]+\] 0 d"


def test_solid_letters_are_filled_with_non_zero_winding():
    """Even-odd fill (ReportLab's default) would punch holes in Devanagari
    conjuncts, so the renderer must ask for non-zero explicitly."""
    content = content_of(render_worksheet(bare_spec(letters="solid")))
    assert re.search(NONZERO_FILL_OP, content), "expected a non-zero fill operator"
    assert not re.search(rb"(?m)^f\*$", content), "even-odd fill must not be used"


def test_outlined_letters_are_stroked_and_not_filled():
    content = content_of(render_worksheet(bare_spec(letters="outlined")))
    assert re.search(STROKE_OP, content), "expected a stroke operator"
    assert not re.search(FILL_OP, content), "outlined letters must not be filled"


def test_dashed_letters_use_a_pdf_dash_array():
    content = content_of(render_worksheet(bare_spec(letters="dashed")))
    assert re.search(DASH_ARRAY, content), "expected a dash array"
    assert re.search(STROKE_OP, content)
    assert not re.search(FILL_OP, content)


def test_outlined_letters_have_no_dash_array():
    content = content_of(render_worksheet(bare_spec(letters="outlined")))
    assert not re.search(DASH_ARRAY, content)


def test_every_letter_style_produces_different_output():
    streams = {
        style: content_of(render_worksheet(bare_spec(letters=style)))
        for style in ("dashed", "dotted", "outlined", "solid")
    }
    assert len(set(streams.values())) == 4


def test_dotted_letters_use_a_zero_length_dash_and_a_round_cap():
    """That combination is how PDF paints a row of dots; a non-zero 'on' length
    would draw dashes instead."""
    content = content_of(render_worksheet(bare_spec(letters="dotted")))
    assert re.search(rb"\[0 [\d.]+\] 0 d", content), "expected a zero-length dash"
    assert re.search(rb"(?m)^1 J$", content), "dots need a round line cap"
    assert re.search(STROKE_OP, content)
    assert not re.search(FILL_OP, content)


def test_dotted_and_dashed_letters_have_different_periods():
    def gaps(style):
        content = content_of(render_worksheet(bare_spec(letters=style)))
        return re.findall(rb"\[([\d.]+) ([\d.]+)\] 0 d", content)

    assert gaps("dotted") != gaps("dashed")


def test_trace_spacing_changes_the_dash_and_dot_period():
    def periods(style, spacing):
        content = content_of(
            render_worksheet(bare_spec(letters=style, trace_spacing=spacing))
        )
        return re.findall(rb"\[[\d.]+ ([\d.]+)\] 0 d", content)

    for style in ("dashed", "dotted"):
        tight = periods(style, "tight")
        wide = periods(style, "wide")
        assert tight and wide
        assert float(tight[0]) < float(wide[0])


def test_solid_letters_are_only_stroked_when_set_to_double(english_font):
    scale = compute_metrics(english_font, "english", 12 * mm).scale
    single = content_of(render_worksheet(bare_spec(letters="solid", solid_layers="single")))
    assert not re.search(rb"(?m)^B$", single), "single-layer solid must fill only"
    assert re.search(rb"(?m)^f$", single), "expected a non-zero fill only"

    heavy = content_of(render_worksheet(
        bare_spec(letters="solid", solid_layers="double", solid_weight=0.8)
    ))
    assert re.search(rb"(?m)^B$", heavy), "expected a fill+stroke operator"
    assert any(abs(width * scale - 0.8) < 0.01 for width in line_widths(heavy))

    # A weight is ignored unless the layer is set to double.
    ignored = content_of(render_worksheet(
        bare_spec(letters="solid", solid_layers="single", solid_weight=0.8)
    ))
    assert not re.search(rb"(?m)^B$", ignored), "single layer must ignore solid_weight"


def test_extra_weight_grows_the_glyph_bbox_so_the_stroke_is_not_clipped():
    """A form's BBox clips it, so the widened outline has to fit inside."""
    plain = glyph_forms(
        PdfReader(BytesIO(render_worksheet(bare_spec(text="o", letters="solid")))).pages[0]
    )
    heavy = glyph_forms(
        PdfReader(
            BytesIO(
                render_worksheet(
                    bare_spec(text="o", letters="solid", solid_layers="double", solid_weight=1.2)
                )
            )
        ).pages[0]
    )
    plain_box = [float(v) for v in next(iter(plain.values()))["/BBox"]]
    heavy_box = [float(v) for v in next(iter(heavy.values()))["/BBox"]]
    assert heavy_box[0] < plain_box[0] and heavy_box[3] > plain_box[3]


def line_widths(content: bytes) -> set[float]:
    return {float(match) for match in re.findall(rb"([\d.]+) w", content)}


def test_letter_thickness_changes_the_stroke_width(english_font):
    """Letters are stroked under a scale matrix, so the emitted width is
    thickness/scale -- it must still measure ``thickness`` on paper."""
    scale = compute_metrics(english_font, "english", 12 * mm).scale
    for thickness in (0.4, 1.6):
        widths = line_widths(
            content_of(
                render_worksheet(
                    bare_spec(letters="outlined", letter_thickness=thickness)
                )
            )
        )
        assert any(
            abs(width * scale - thickness) < 0.01 for width in widths
        ), f"no stroke width matching {thickness}pt in {widths}"


def test_letter_darkness_changes_the_gray_level():
    def fill_grays(darkness):
        content = content_of(
            render_worksheet(bare_spec(letters="solid", letter_darkness=darkness))
        )
        return {float(match) for match in re.findall(rb"([\d.]+) g", content)}

    assert 0.0 in fill_grays(100)  # pure black
    assert 0.8 in fill_grays(20)  # faint
    assert fill_grays(100) != fill_grays(20)


def test_guide_darkness_and_thickness_are_applied():
    content = content_of(
        render_worksheet(bare_spec(guide_darkness=100, guide_thickness=1.5))
    )
    assert 1.5 in line_widths(content)
    assert 0.0 in {float(m) for m in re.findall(rb"([\d.]+) G", content)}


def test_guide_style_overrides_every_line():
    """'classic' dashes only the aiming lines; the other styles apply to all of
    them, base line included."""
    def guides(style):
        return content_of(
            render_worksheet(
                bare_spec(
                    text="\n", top_line=True, mid_line=True, guide_style=style
                )
            )
        )

    assert re.search(rb"\[[\d.]+ [\d.]+\] 0 d", guides("classic"))
    assert not re.search(rb"\] 0 d", guides("solid")), "all-solid must set no dash"
    assert re.search(rb"\[0 [\d.]+\] 0 d", guides("dotted")), "expected dotted rules"
    assert len({guides(s) for s in ("classic", "solid", "dashed", "dotted")}) == 4


def test_base_line_is_always_drawn_even_with_every_guide_off():
    content = content_of(render_worksheet(bare_spec(text="\n", letters="solid")))
    assert re.search(rb"l S", content), "the base line must always be stroked"


def test_hindi_worksheet_renders():
    pdf = render_worksheet(
        WorksheetSpec(lang="hindi", font_path=HINDI_FONT, text="कि की क्ष त्र हिंदी")
    )
    assert pdf.startswith(b"%PDF-")
    assert page_count(pdf) == 1


def test_line_height_controls_rows_per_page():
    small = render_worksheet(bare_spec(text="a\n" * 40, line_height_mm=8))
    large = render_worksheet(bare_spec(text="a\n" * 40, line_height_mm=25))
    assert page_count(large) > page_count(small)


def test_double_spacing_needs_more_pages():
    single = render_worksheet(bare_spec(text="a\n" * 30, line_spacing="single"))
    double = render_worksheet(bare_spec(text="a\n" * 30, line_spacing="double"))
    assert page_count(double) > page_count(single)


def test_orientation_and_paper_size_change_the_media_box():
    tall = PdfReader(BytesIO(render_worksheet(bare_spec()))).pages[0].mediabox
    wide = PdfReader(
        BytesIO(render_worksheet(bare_spec(orientation="wide")))
    ).pages[0].mediabox
    letter = PdfReader(
        BytesIO(render_worksheet(bare_spec(paper_size="Letter")))
    ).pages[0].mediabox

    assert float(tall.height) > float(tall.width)
    assert float(wide.width) > float(wide.height)
    assert abs(float(tall.width) - 210 * mm) < 1
    assert abs(float(letter.width) - 8.5 * 72) < 1


def test_five_thousand_characters_paginates_and_stays_fast():
    text = "\n".join("the quick brown fox jumps over the lazy dog" for _ in range(113))
    assert 4000 < len(text) <= 5000
    started = time.perf_counter()
    pdf = render_worksheet(bare_spec(text=text, rows_per_block=3))
    elapsed = time.perf_counter() - started
    assert page_count(pdf) > 5
    # The glyph outline cache is what makes this viable; without it this crawls.
    assert elapsed < 20.0, f"took {elapsed:.1f}s"


def test_each_distinct_glyph_is_emitted_once_as_a_reusable_form(english_font):
    """`aaaa aaaa` must define a single form, not eight copies of the path."""
    pdf = render_worksheet(bare_spec(text="aaaa aaaa", rows_per_block=6))
    forms = glyph_forms(PdfReader(BytesIO(pdf)).pages[0])
    assert len(forms) == 1
    assert next(iter(forms)).startswith("/")


def test_form_count_matches_the_distinct_inked_glyphs(english_font):
    text = "the quick brown fox"
    pdf = render_worksheet(bare_spec(text=text, rows_per_block=3))
    glyphs, _ = shape(english_font, text)
    expected = {g.gid for g in glyphs if glyph_contours(english_font, g.gid)}
    forms = glyph_forms(PdfReader(BytesIO(pdf)).pages[0])
    assert len(forms) == len(expected)


def outline_bounds(font, gid):
    points = [
        pt
        for contour in glyph_contours(font, gid)
        for seg in contour
        for pt in seg[1:]
    ]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def test_glyph_form_bbox_does_not_clip_the_outline(english_font):
    """A form's BBox clips its content, so it must contain the whole glyph.

    Descenders (g j p q y) are the ones that get chopped if the box is wrong.
    """
    pdf = render_worksheet(bare_spec(text="gjpqy bdhkl", letters="outlined"))
    forms = glyph_forms(PdfReader(BytesIO(pdf)).pages[0])
    assert forms
    for name, form in forms.items():
        gid = int(re.search(r"wpGlyph(\d+)", name).group(1))
        bx0, by0, bx1, by1 = (float(v) for v in form["/BBox"])
        gx0, gy0, gx1, gy1 = outline_bounds(english_font, gid)
        assert bx0 < gx0 and gx1 < bx1, f"{name} clipped horizontally"
        assert by0 < gy0 and gy1 < by1, f"{name} clipped vertically"


def test_reusing_glyphs_keeps_a_long_worksheet_small():
    text = "\n".join("the quick brown fox jumps over the lazy dog" for _ in range(113))
    pdf = render_worksheet(bare_spec(text=text, rows_per_block=3))
    per_page = len(pdf) / page_count(pdf)
    assert per_page < 60_000, f"{per_page:.0f} bytes/page suggests glyph reuse broke"


def test_header_elements_appear_only_when_asked():
    plain = render_worksheet(bare_spec())
    titled = render_worksheet(
        bare_spec(page_title="My Sheet", instructions="Trace it", show_date_line=True)
    )
    assert len(titled) > len(plain)
