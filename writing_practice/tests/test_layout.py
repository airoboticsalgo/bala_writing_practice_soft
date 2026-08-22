from reportlab.lib.units import mm

from app.render.guides import compute_metrics
from app.render.layout import build_rows, paginate, rows_per_page, wrap_line
from app.render.paint import text_width


def scale_for(font, lang="english"):
    return compute_metrics(font, lang, 12 * mm).scale


def test_short_line_is_not_wrapped(english_font):
    assert wrap_line(english_font, "cat dog", scale_for(english_font), 500) == ["cat dog"]


def test_long_line_wraps_within_the_width(english_font):
    scale = scale_for(english_font)
    text = "the quick brown fox jumps over the lazy dog again and again"
    max_width = 200.0
    lines = wrap_line(english_font, text, scale, max_width)
    assert len(lines) > 1
    for line in lines:
        assert text_width(english_font, line, scale) <= max_width
    assert " ".join(lines) == text  # nothing lost, nothing duplicated


def test_single_word_longer_than_a_line_is_hard_broken(english_font):
    scale = scale_for(english_font)
    lines = wrap_line(english_font, "supercalifragilisticexpialidocious", scale, 60.0)
    assert len(lines) > 1
    assert "".join(lines) == "supercalifragilisticexpialidocious"
    for line in lines:
        assert text_width(english_font, line, scale) <= 60.0


def test_hindi_wraps_on_measured_widths(hindi_font):
    scale = scale_for(hindi_font, "hindi")
    text = "कमल पानी किताब बादल तितली मिठाई सूरज नगर मगर सरल"
    lines = wrap_line(hindi_font, text, scale, 180.0)
    assert len(lines) > 1
    for line in lines:
        assert text_width(hindi_font, line, scale) <= 180.0


def test_blank_input_line_becomes_one_blank_row(english_font):
    rows = build_rows(
        "cat\n\ndog",
        english_font,
        scale_for(english_font),
        500,
        rows_per_block=2,
        following_lines="repeat",
    )
    assert [r.text for r in rows] == ["cat", "cat", "", "dog", "dog"]


def test_following_lines_blank_leaves_the_rest_empty(english_font):
    rows = build_rows(
        "cat",
        english_font,
        scale_for(english_font),
        500,
        rows_per_block=4,
        following_lines="blank",
    )
    assert [r.text for r in rows] == ["cat", "", "", ""]


def test_rows_per_block_controls_repetitions(english_font):
    for count in (1, 3, 6):
        rows = build_rows(
            "cat",
            english_font,
            scale_for(english_font),
            500,
            rows_per_block=count,
            following_lines="repeat",
        )
        assert len(rows) == count


def test_each_wrapped_segment_gets_its_own_block(english_font):
    scale = scale_for(english_font)
    rows = build_rows(
        "the quick brown fox jumps over the lazy dog",
        english_font,
        scale,
        120.0,
        rows_per_block=2,
        following_lines="repeat",
    )
    assert len(rows) % 2 == 0
    assert len(rows) > 2


def test_rows_per_page_fits_a_final_row_without_a_trailing_gap():
    # pitch 30 = row 24 + gap 6. The last row on a page needs no trailing gap,
    # so 114pt fits 4 rows (3 x 30 + 24) even though 4 x 30 would not fit.
    assert rows_per_page(114.0, 30.0, 24.0) == 4
    assert rows_per_page(100.0, 30.0, 24.0) == 3
    assert rows_per_page(90.0, 30.0, 24.0) == 3
    assert rows_per_page(5.0, 30.0, 24.0) == 1


def test_paginate_chunks_and_never_returns_nothing():
    rows = [object()] * 10
    assert [len(page) for page in paginate(rows, 4)] == [4, 4, 2]
    assert paginate([], 4) == [[]]
