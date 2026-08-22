"""The tests that matter most: Devanagari must be shaped, not just mapped."""

from reportlab.lib.units import mm

from app.render.glyphs import glyph_contours, ink_extents, probe_top
from app.render.guides import compute_metrics
from app.render.shaper import advance_width, shape

NOTDEF = 0


def gid(font, char):
    return font.glyph_order.index(font.cmap[ord(char)])


def test_i_matra_is_reordered_before_its_consonant(hindi_font):
    """`कि` is typed क + ि but must be *drawn* ि first. This is the whole point.

    The matra glyph is asserted only by position, not identity: the font picks a
    width-matched variant (uni093F.04) rather than the plain cmap glyph.
    """
    glyphs, _ = shape(hindi_font, "कि")
    assert len(glyphs) == 2
    assert glyphs[1].gid == gid(hindi_font, "क"), "consonant must be drawn second"
    assert glyphs[0].gid != gid(hindi_font, "क")
    assert glyph_contours(hindi_font, glyphs[0].gid), "the matra must have ink"


def test_ii_matra_stays_after_its_consonant(hindi_font):
    glyphs, _ = shape(hindi_font, "की")
    assert len(glyphs) == 2
    assert glyphs[0].gid == gid(hindi_font, "क"), "consonant must be drawn first"
    assert glyphs[1].gid != gid(hindi_font, "क")


def test_conjuncts_ligate_into_fewer_glyphs(hindi_font):
    for cluster in ("क्ष", "त्र", "ज्ञ"):
        glyphs, _ = shape(hindi_font, cluster)
        assert len(glyphs) < len(cluster), f"{cluster} was not ligated"


def test_no_notdef_glyphs_in_hindi_samples(hindi_font):
    for sample in ("कि", "की", "क्ष", "त्र", "हिंदी", "कमल", "पानी", "१२३", "माँ"):
        glyphs, _ = shape(hindi_font, sample)
        assert glyphs, sample
        assert all(g.gid != NOTDEF for g in glyphs), sample


def test_hindi_word_produces_inked_glyphs(hindi_font):
    """`हिंदी` must draw ink for each visible part.

    Not *every* glyph carries ink: the anusvara is absorbed into a combined
    i-matra ligature and the font emits a zero-width ``NullMark`` in its place,
    which correctly has no outline.
    """
    glyphs, _ = shape(hindi_font, "हिंदी")
    inked = [g for g in glyphs if glyph_contours(hindi_font, g.gid)]
    assert len(inked) >= 4


def test_english_shaping_is_one_glyph_per_letter(english_font):
    glyphs, _ = shape(english_font, "cat")
    assert [g.gid for g in glyphs] == [gid(english_font, c) for c in "cat"]


def test_advance_width_grows_with_text(english_font):
    assert advance_width(english_font, "iii") < advance_width(english_font, "mmm")
    assert advance_width(english_font, "") == 0.0


def test_shiro_rekha_sits_on_the_letters_not_above_them(hindi_font):
    """The headline must equal the ink top of a bare consonant."""
    metrics = compute_metrics(hindi_font, "hindi", 12 * mm)
    consonant_top = ink_extents(hindi_font, "क")[1] * metrics.scale
    assert abs(metrics.top - consonant_top) < 0.01
    # ...and the ascender would have been wrong: it is genuinely higher.
    assert hindi_font.ascender > ink_extents(hindi_font, "क")[1]


def test_upper_matra_line_is_above_the_headline(hindi_font):
    metrics = compute_metrics(hindi_font, "hindi", 12 * mm)
    assert metrics.upper > metrics.top


def test_lower_matra_room_is_below_the_baseline(hindi_font):
    metrics = compute_metrics(hindi_font, "hindi", 12 * mm)
    assert metrics.descender < 0


def test_english_line_height_is_the_ascender_ink_height(english_font):
    """A 12 mm line height must measure 12 mm from base line to the top of `b`."""
    metrics = compute_metrics(english_font, "english", 12 * mm)
    assert abs(metrics.top - 12 * mm) < 0.01
    b_top = ink_extents(english_font, "b")[1] * metrics.scale
    assert abs(b_top - 12 * mm) < 0.01


def test_english_guides_are_ordered_correctly(english_font):
    metrics = compute_metrics(english_font, "english", 12 * mm)
    assert metrics.descender < 0 < metrics.mid < metrics.top
    x_top = ink_extents(english_font, "x")[1] * metrics.scale
    assert abs(metrics.mid - x_top) < 0.01


def test_hhea_ascender_would_have_been_the_wrong_reference(english_font):
    """Guards the bug this design avoids: Andika's hhea ascender exceeds its em."""
    assert english_font.ascender > english_font.upem
    assert probe_top(english_font, "bdhkl") < english_font.ascender
