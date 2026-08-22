# AGENTS.md — writing_practice

Project info for anyone (human or agent) working in this repo. Spec: `PROMPT.md`.

## Commands

Windows paths shown; on Linux/macOS use `.venv/bin/python`.

| Task | Command |
|---|---|
| Run the app | `run.bat` (or `.venv\Scripts\python wsgi.py`) |
| Tests | `.venv\Scripts\python -m pytest` |
| Pre-flight check | `.venv\Scripts\python -m tools.check_setup` |
| Install runtime deps | `.venv\Scripts\python -m pip install -r requirements.txt` |
| Install dev deps | `.venv\Scripts\python -m pip install -r requirements-dev.txt` |

Python 3.12 in `.venv`. Runtime deps are **only** Flask, reportlab, uharfbuzz, fonttools — all pinned
and all pure pip wheels. Ask before adding another. `pytest.ini` sets `pythonpath = .` so `import app`
works from the repo root.

## Architecture

- `app/render/` is the renderer and must never touch Flask globals. Entry point:
  `render_worksheet(spec) -> bytes`. `WorksheetSpec` (frozen dataclass) is the only input.
- `shaper.py` (uharfbuzz) → `glyphs.py` (fontTools outlines, cached) → `paint.py` (reportlab paths).
- `spec.py` owns every option, its allowed values and its clamping. `form_values()` powers the form
  round-trip; `from_form()` validates. Add new options there first.
- Pages 2 and 3 share `templates/worksheet_form.html`, parameterised by `lang`.
- Config: `config/app.conf` (INI). Every key needs a default in `app/config.py::DEFAULTS`.

## Gotchas discovered the hard way

- **Font metric tables lie about ink height.** Andika's `hhea.ascender` is 2500 on a 2048 em (it
  includes line gap). Guide positions come from measured outlines (`glyphs.probe_top/probe_bottom`),
  never from `hhea`/`OS/2`. Same reason the Hindi shiro-rekha is derived from the ink top of `क`.
- **ReportLab defaults to even-odd fill** (`f*`). TrueType outlines need non-zero winding, so
  `drawPath` is always called with `fillMode=FILL_NON_ZERO`; otherwise overlapping contours in
  Devanagari conjuncts get punched out.
- **Line widths and dashes scale with the CTM.** Letters are drawn under a scale matrix, so
  `paint._apply_style` divides thickness and dash period by the scale. Tests assert
  `emitted_width * scale == thickness`.
- **A Form XObject's BBox clips its content.** `GlyphPainter._bbox` derives it from the glyph outline
  plus padding for the stroke. Get it wrong and descenders get chopped.
- **`rl_config.useA85 = 0`** is set in `app/render/page.py`. Streams are already Flate-compressed and
  reportlab's pure-Python base85 encoder cost more than all the rest of the rendering combined.
- **Dash and dot lengths are tuned by eye** (`paint.trace_periods`, line_height/24 and /14, times
  the user's tight/normal/wide factor). Longer dashes shatter Devanagari conjuncts into
  unrecognisable fragments. Both the PDF and the SVG preview must call that one helper.
- **A dot is a zero-length dash plus a round cap** (`[0 gap] 0 d` with `1 J`), for letters and for
  dotted guide lines. A non-zero "on" length gives dashes, not dots.
- **Solid letters are fill-only unless `solid_weight > 0`**, which switches the paint operator from
  `f` to `B` and needs the glyph form's BBox padded by the stroke, or the emboldened edge is clipped.
- Shaped glyph ids are **not** cmap glyph ids: Noto picks width-matched matra variants
  (`uni093F.04`), so never assert on glyph identity from `cmap` — assert on order and ink.
- A shaped run can legitimately contain ink-less glyphs (`NullMark`) when a mark is absorbed into a
  ligature. Don't treat that as a failure.

## Verifying rendering changes

There is no rasterizer in the dependencies. To eyeball a PDF, temporarily
`pip install pypdfium2`, render pages to PNG, look at them, then **uninstall it** — it must not end
up in `requirements*.txt`.

Always check a Hindi sample (`कि की क्ष त्र हिंदी`) after touching the render path, and confirm the
shiro-rekha sits *on* the letters rather than above them.
