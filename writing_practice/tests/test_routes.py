def test_home_links_to_both_languages(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/english/writing/handwriting/print-practice" in body
    assert "/hindi/writing/handwriting/print-practice" in body


def test_english_form_loads(client):
    response = client.get("/english/writing/handwriting/print-practice")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Print Handwriting Practice" in body
    assert "Top line" in body
    assert "5,000 characters" in body


def test_hindi_form_loads_with_hindi_guides(client):
    response = client.get("/hindi/writing/handwriting/print-practice")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Shiro-rekha" in body
    assert "बारहखड़ी" in body
    assert "Top line" not in body


def test_forms_expose_the_style_controls(client):
    for lang in ("english", "hindi"):
        body = client.get(f"/{lang}/writing/handwriting/print-practice").get_data(
            as_text=True
        )
        assert 'value="dotted"' in body
        assert 'name="guide_style"' in body
        assert 'name="trace_spacing"' in body
        assert 'name="solid_layers"' in body
        assert 'name="solid_weight"' in body


def test_generate_accepts_the_style_controls(client):
    response = client.post(
        "/english/writing/handwriting/print-practice/generate",
        data={
            "text": "adg",
            "letters": "dotted",
            "trace_spacing": "wide",
            "letter_thickness": "2.5",
            "guide_style": "dotted",
            "guide_thickness": "0.15",
            "solid_layers": "single",
            "solid_weight": "0.8",
            "top_line": "on",
        },
    )
    assert response.status_code == 200
    assert response.get_data().startswith(b"%PDF-")


def test_unknown_language_is_404(client):
    assert client.get("/klingon/writing/handwriting/print-practice").status_code == 404


def test_generate_returns_an_inline_pdf(client):
    response = client.post(
        "/english/writing/handwriting/print-practice/generate",
        data={"text": "cat dog", "page_title": "My Sheet"},
    )
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"].startswith("inline;")
    assert "my-sheet-" in response.headers["Content-Disposition"]
    assert response.get_data().startswith(b"%PDF-")


def test_generate_hindi_returns_a_pdf(client):
    response = client.post(
        "/hindi/writing/handwriting/print-practice/generate",
        data={"text": "कि की क्ष", "shiro_rekha": "on"},
    )
    assert response.status_code == 200
    assert response.get_data().startswith(b"%PDF-")


def test_empty_text_re_renders_the_form_with_an_error(client):
    response = client.post(
        "/english/writing/handwriting/print-practice/generate", data={"text": "  "}
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "Nothing was generated" in body
    assert "type some text" in body
    assert "Traceback" not in body


def test_over_limit_text_re_renders_the_form_with_an_error(client):
    response = client.post(
        "/english/writing/handwriting/print-practice/generate",
        data={"text": "a" * 5001},
    )
    assert response.status_code == 400
    assert "limit is 5,000" in response.get_data(as_text=True)


def test_rejected_submission_keeps_every_choice(client):
    response = client.post(
        "/english/writing/handwriting/print-practice/generate",
        data={
            "text": "",
            "page_title": "Rohan's Sheet",
            "instructions": "Trace carefully",
            "line_height_mm": "20",
            "letters": "outlined",
            "solid_layers": "double",
            "solid_weight": "0.6",
            "guide_style": "dotted",
            "trace_spacing": "wide",
            "line_spacing": "double",
            "following_lines": "blank",
            "rows_per_block": "5",
            "paper_size": "Letter",
            "orientation": "wide",
            "child_name": "Rohan",
            "mid_line": "on",
        },
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "Rohan&#39;s Sheet" in body
    assert "Trace carefully" in body
    assert '<option value="20" selected>20 mm</option>' in body
    assert '<option value="5" selected>5</option>' in body
    assert 'value="outlined"\n               checked' in body or 'value="outlined" checked' in body
    assert '<option value="Letter" selected>Letter</option>' in body
    assert '<option value="wide" selected>wide</option>' in body
    assert 'value="dotted" checked' in body
    assert '<option value="double" selected>double</option>' in body


def test_generate_rejects_an_unknown_language(client):
    response = client.post(
        "/klingon/writing/handwriting/print-practice/generate", data={"text": "a"}
    )
    assert response.status_code == 404


def test_static_assets_are_served(client):
    assert client.get("/static/css/style.css").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200
