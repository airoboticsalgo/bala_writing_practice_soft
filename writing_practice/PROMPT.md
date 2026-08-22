# writing_practice — Build Prompt / Specification

> This file was the **implementation prompt**; the project is now built to it.
> Sections marked **as built** were corrected during implementation — trust those over the original
> intent. See `README.md` for usage and `AGENTS.md` for the gotchas found along the way.

---

## 1. Goal

A small **Python Flask** application that generates **printable PDF handwriting worksheets** for
children practising **English print** and **Hindi (Devanagari) print** letters and words.

Modelled on `https://www.worksheetworks.com/english/writing/handwriting/print-practice.html`:
the user types text (or picks a preset), sets the options in §3, clicks **Generate**, and gets a
print-ready PDF.

Audience: one family, run locally on Windows (`run.bat`) or Linux/mac (`run.sh`). No login, no DB.

---

## 2. Pages (URL structure must mirror the reference site)

| Page | Route | Purpose |
|---|---|---|
| Page 1 | `/` | Landing page. Two big cards: **English Handwriting** and **Hindi Handwriting (हिंदी लेखन)**. Links to page 2 / page 3. |
| Page 2 | `/english/writing/handwriting/print-practice` | English worksheet builder form |
| Page 3 | `/hindi/writing/handwriting/print-practice` | Hindi worksheet builder form |
| POST | `/<lang>/writing/handwriting/print-practice/generate` | Accepts the form, returns `application/pdf` |

Notes:
- Pages 2 and 3 share **one Jinja template** (`worksheet_form.html`) parameterised by language;
  do not duplicate it. Only the presets panel, the guide-line labels, and the default font differ.
- Plain, high-contrast, child-friendly UI. One hand-written CSS file, **no CSS framework, no JS
  framework**. Vanilla JS only, for: character counter, preset click-to-fill, options panel
  collapse, and disabling `letter_thickness` when `letters = solid`.
- PDF returned inline (`Content-Disposition: inline; filename=...`) so it previews in the browser.
- Every option below round-trips: after generating, the form must come back with the user's choices
  still selected (they will tweak one setting and re-generate many times).

---

## 3. Worksheet options (the form) — authoritative list

### Content

| Field | Control | Default | Notes |
|---|---|---|---|
| `page_title` | text | `Handwriting Practice` | Printed centred at the top of every page |
| `instructions` | text (optional) | empty | Small italic line under the title. Omit the line entirely if blank |
| `text` | textarea, **max 5,000 chars** | empty | The practice content |
| `preset` | chips / dropdown | — | Fills the textarea (§6) |
| `case` (English only) | select | `as-typed` | `as-typed` / `UPPERCASE` / `lowercase` / `Title Case` |
| `child_name`, `show_date_line` | text, checkbox | empty, off | Optional `Name: ______  Date: ______` header row |

**Text semantics — get these exactly right:**
- Each input line becomes one **writing line** on the worksheet.
- A line **too long to fit** the printable width **wraps** onto the next writing line. Wrap on
  whitespace where possible; hard-break only a single word longer than the full line.
  Wrapping must be measured from **real shaped advance widths**, not an estimated char count.
- A **blank input line produces a blank writing line** (ruled guides, no letters) — it is a
  deliberate free-practice row, not something to skip.
- 5,000 characters is dozens of pages; pagination must be streaming/loop-based, not "build one huge
  page and hope".

### Line guides

The **base line is always drawn**. These are optional checkboxes, on by default unless noted:

| Language | Checkbox | Meaning |
|---|---|---|
| English | `top_line` | Ascender / cap line |
| English | `mid_line` | x-height (mean) line — drawn **dashed** |
| English | `descender_line` | Below the base line, for `g j p q y` (default **off**) |
| Hindi | `shiro_rekha` | Headline the letters hang from — the Devanagari equivalent of a top line |
| Hindi | `upper_matra_line` | Dashed guide above the headline for ि ी े ै ो ौ ं |
| Hindi | `lower_matra_line` | Dashed guide below the base line for ु ू ृ (default **off**) |

| Field | Control | Default |
|---|---|---|
| `line_height` | select: 8 / 10 / 12 / 15 / 20 / 25 mm | 12 mm — base line to top line (see §4.4) |
| `guide_darkness` | slider 0–100 % black | 30 % |
| `guide_thickness` | select 0.25 / 0.5 / 0.75 / 1.0 / 1.5 pt | 0.5 pt |

### Letters

| Field | Control | Default | Notes |
|---|---|---|---|
| `letters` | radio: `dashed` / `outlined` / `solid` | `dashed` | How the model letters are drawn — see §4.3 |
| `letter_darkness` | slider 0–100 % black | 40 % | 100 % = pure black |
| `letter_thickness` | select 0.4 / 0.6 / 0.8 / 1.2 / 1.6 pt | 0.6 pt | Stroke width. **Ignored when `letters = solid`** — disable the control in the UI |

### Line spacing & repetition

| Field | Control | Default | Notes |
|---|---|---|---|
| `line_spacing` | radio: `single` / `double` | `single` | `double` inserts a full blank writing line's worth of space between rows — room for a big pencil grip |
| `following_lines` | radio: `repeat` / `blank` | `repeat` | `repeat`: the text is drawn again on every following line of the block. `blank`: only the first line shows the model, the rest are ruled but empty |
| `rows_per_block` | select 1–20 | 3 | Writing lines produced per input line (labelled "Lines per page") |

### Layout & Presentation

| Field | Control | Default |
|---|---|---|
| `paper_size` | select: `A4` / `Letter` | A4 |
| `orientation` | radio: `tall` (portrait) / `wide` (landscape) | tall |

Server-side validation: empty `text` and `text` over 5,000 chars both re-render the form with an
inline error message and HTTP 400 — never a traceback, never a blank PDF. Clamp every numeric field
to its allowed set rather than trusting the POST body.

---

## 4. Rendering engine — read this before writing any renderer code

### 4.1 The two hard constraints

1. **Devanagari needs OpenType shaping.** Matras reorder visually (`कि` — the `ि` is typed after the
   `क` but drawn before it) and conjuncts ligate (`क्ष`, `त्र`). ReportLab's `drawString()` and any
   naive codepoint-to-glyph loop produce wrong output. Shaping is mandatory.
2. **`dashed` and `outlined` letters plus `letter_thickness` require the glyph *outline*, not a
   glyph bitmap.** You cannot dash or variable-stroke a rasterised letter. This rules out
   Pillow/Raqm text drawing, which can only fill (or crudely stroke) glyphs.

Together these force one design: **shape the text, extract glyph outlines as vector paths, and draw
the paths yourself.**

### 4.2 The pipeline

1. **Shape** — `uharfbuzz`: feed the string + font blob, get back a list of
   `(glyph_id, x_advance, y_advance, x_offset, y_offset)` in font units. Correct Devanagari
   reordering and ligatures come free, and the advances are what §3 line-wrapping measures with.
2. **Outline** — `fontTools`: `TTFont(path).getGlyphSet()`, draw each `glyph_id` into a pen that
   subclasses `fontTools.pens.basePen.BasePen`. `BasePen` resolves composite glyphs and converts
   TrueType quadratics to cubics automatically, so the pen only needs `moveTo / lineTo / curveTo /
   closePath`. Works for both TrueType and CFF/OTF fonts.
3. **Cache** — memoise outlines on `(font_path, glyph_id)`. A worksheet repeats the same handful of
   glyphs hundreds of times; without the cache 5,000 characters will crawl.
4. **Draw** — `reportlab` canvas. Scale font units to points, translate to the pen position, and
   emit a `canvas.beginPath()` path. ReportLab gives real vector output, native dash patterns, and
   exact stroke widths.
5. **Reuse** *(as built)* — emit each distinct glyph **once** as a Form XObject and invoke it with a
   translate/scale matrix, the way embedded fonts work. Inlining every path made a 5,000-character
   sheet 5 MB and 4.5 s; with forms it is ~550 KB and ~0.8 s. Two consequences to respect: a form's
   `BBox` **clips** its content (derive it from the glyph outline plus stroke padding), and line
   widths and dash periods must be divided by the scale because PDF measures them in the user space
   in force when the path is stroked.

Result: a true vector PDF that prints crisply at any size, with only pip-installable
wheels — no GTK, no Pango, no headless browser.

Rejected, for the record: **Pillow/Raqm raster** (cannot dash or stroke outlines — this was the
earlier plan and the `dashed`/`outlined` requirement kills it); **WeasyPrint** (correct shaping but
needs GTK DLLs on Windows, hostile to a one-click `run.bat`); **plain ReportLab text** (broken
Devanagari); **headless Chrome** (heavyweight dependency).

### 4.3 Mapping `letters` onto path painting

| `letters` | Painting | Detail |
|---|---|---|
| `solid` | fill, no stroke | Use **non-zero winding** so counters (`o`, `a`, `ठ`) come out hollow. *(as built)* ReportLab defaults to **even-odd**, so `fillMode=FILL_NON_ZERO` must be passed explicitly or overlapping contours in Devanagari conjuncts get punched out. Ignore `letter_thickness` |
| `outlined` | stroke, no fill | `setLineWidth(letter_thickness)`; hollow letter the child colours/traces inside |
| `dashed` | stroke, no fill, dashed | `canvas.setDash([on, off])`. PDF dash arrays follow bezier curves natively, so no manual curve flattening. Scale the dash period with `line_height`. *(as built)* `line_height/8` was far too coarse — it shattered `क्ष` and `हिंदी` into untraceable fragments. Tuned by eye to **`line_height/24`** |

`letter_darkness` and `guide_darkness` are percent-black → `setFillGray(1 - pct/100)` /
`setStrokeGray(1 - pct/100)`. Keep guides greyscale so cheap printers don't smear colour.

### 4.4 Vertical metrics — *(as built: measure ink, never the metric tables)*

Define one scale factor and derive everything from it, so `line_height` is physically accurate.

The original plan used `hhea.ascender` and `OS/2.sxHeight`. **That is wrong.** Andika reports an
`hhea.ascender` of 2500 on a 2048 em because it bakes in line gap, so a "12 mm line height" would
have rendered letters 6.7 mm tall. Every guide is measured from the **ink** of a probe character
instead:

```
English: scale     = line_height_pt / ink_top("b")   # base line -> top line == line_height
         mid_line  = ink_top("x")    * scale         # x-height
         descender = ink_bottom("p") * scale         # negative, below the base line

Hindi:   scale     = line_height_pt / ink_top("क")   # base line -> shiro-rekha == line_height
         upper     = ink_top("ी")    * scale         # upper-matra guide, above the headline
         descender = ink_bottom("ु") * scale
```

The **shiro-rekha sits at the headline the glyphs hang from**, which is emphatically not the font's
ascender — the ascender includes room for upper matras. The top edge of a bare `क` *is* the headline.
Getting this wrong (guide floating above the letters) is the most visible possible bug on a Hindi
sheet, so it has a dedicated test.

For Hindi, `line_height` therefore means base line → shiro-rekha, i.e. the letter body height, which
is the part of a Devanagari letter a child actually writes.

Row pitch = `line_height + descender room + gap`, where `gap` doubles when
`line_spacing = double`.

### 4.5 Structure

All rendering lives in `app/render/`, behind one entry point:

```
render_worksheet(spec: WorksheetSpec) -> bytes      # PDF bytes
```

`WorksheetSpec` is a frozen `@dataclass` built by `from_form()`. The renderer must never touch
`request`, `session`, or any Flask global — it has to be unit-testable and callable from a script.

---

## 5. Fonts

Ship fonts in `app/static/fonts/`, **OFL/Apache licensed only**, with each font's license file
alongside. Never download a font at runtime.

- English print model: **Andika** (SIL, OFL) — built for literacy teaching, single-storey `a` and
  `g`, which is what children are actually taught to write. Fallback: **ABeeZee**.
- Hindi: **Noto Sans Devanagari** (OFL) — use a **static instance** TTF, not the variable font.
  *(as built)* the upstream static TTF would not download reliably, so the variable font was fetched
  and instanced at `wght=400, wdth=100` with `fontTools.varLib.instancer`. Optional second: **Mukta**.
- Browser UI: system font stack only.

`font` is a form dropdown listing only fonts actually present on disk. At startup, log the fonts
found; if the configured default is missing, fail with the expected path in the message.

---

## 6. Presets (data files, not hardcoded in templates)

`app/data/hindi_presets.py`:
- **स्वर**: अ आ इ ई उ ऊ ऋ ए ऐ ओ औ अं अः
- **व्यंजन**: क ख ग घ ङ / च छ ज झ ञ / ट ठ ड ढ ण / त थ द ध न / प फ ब भ म / य र ल व / श ष स ह /
  क्ष त्र ज्ञ श्र
- **मात्राएँ**: on a carrier consonant — का कि की कु कू के कै को कौ कं कः
- **बारहखड़ी**: full matra series, one input line per consonant
- **अंक**: १ २ ३ ४ ५ ६ ७ ८ ९ ०
- **सरल शब्द**: घर, माँ, नल, कमल, फल, बस, आम, पानी, किताब, सूरज
- **दो अक्षर / तीन अक्षर** word sets

`app/data/english_presets.py`: A–Z, a–z, 0–9, vowels, CVC words (cat, dog, sun…), sight words,
days of the week, months, blank practice sheet.

---

## 7. Project layout

```
writing_practice/
├── app/
│   ├── __init__.py            # create_app(), config load, blueprints
│   ├── routes/
│   │   ├── home.py            # page 1
│   │   └── practice.py        # pages 2 & 3 + /generate
│   ├── render/
│   │   ├── __init__.py        # render_worksheet(spec) -> bytes
│   │   ├── spec.py            # WorksheetSpec + from_form() validation/clamping
│   │   ├── shaper.py          # uharfbuzz shaping -> positioned glyph ids
│   │   ├── glyphs.py          # fontTools outline pen + outline cache
│   │   ├── paint.py           # solid / outlined / dashed path painting
│   │   ├── guides.py          # base/top/mid/descender, shiro-rekha, matra lines
│   │   ├── layout.py          # wrapping, row pitch, pagination
│   │   ├── page.py            # canvas setup, title, instructions, name/date header
│   │   └── fonts.py           # font discovery, metrics, caching
│   ├── data/{hindi,english}_presets.py
│   ├── templates/{base,home,worksheet_form}.html
│   └── static/
│       ├── css/style.css
│       ├── js/app.js
│       └── fonts/            # Andika, NotoSansDevanagari + LICENSE files
├── config/app.conf           # §8
├── tests/{test_spec,test_layout,test_render,test_routes}.py
├── output/                   # saved PDFs when enabled (gitignored)
├── requirements.txt
├── requirements-dev.txt
├── run.bat
├── run.sh
├── .gitignore
├── AGENTS.md
└── README.md
```

---

## 8. `config/app.conf`

INI, read with `configparser`. **Every key needs an in-code default** so a missing or partial file
still boots. Env override: `WRITING_PRACTICE_CONFIG=<path>`.

```ini
[server]
host = 127.0.0.1
port = 5000
debug = true

[worksheet]
page_title = Handwriting Practice
paper_size = A4
orientation = tall
margin_mm = 12
max_text_chars = 5000
line_height_mm = 12
rows_per_block = 3
line_spacing = single
following_lines = repeat

[guides]
darkness = 30
thickness = 0.5
english_top_line = true
english_mid_line = true
english_descender_line = false
hindi_shiro_rekha = true
hindi_upper_matra_line = true
hindi_lower_matra_line = false

[letters]
style = dashed
darkness = 40
thickness = 0.6

[fonts]
fonts_dir = app/static/fonts
english_default = Andika-Regular.ttf
hindi_default = NotoSansDevanagari-Regular.ttf

[output]
save_generated = false
output_dir = output
```

---

## 9. Dependencies

`requirements.txt` — pin exact versions, each released **at least 7 days ago**, no floating ranges.
*(as built)*:

```
Flask==3.1.3
reportlab==5.0.0
uharfbuzz==0.56.0
fonttools==4.63.0
```

reportlab 5.0.1 was skipped: it was published the day the project was built and so fails the 7-day
rule. `requirements-dev.txt` adds `pytest==9.1.1` and `pypdf==6.15.0` (page counts and content
streams in tests).

No rasterizer is included, so visual checks mean installing `pypdfium2` temporarily and uninstalling
it afterwards — see `AGENTS.md`.

All four have prebuilt Windows wheels and need no system libraries. **Stop and ask before adding
anything else.**

---

## 10. `run.bat` / `run.sh`

Idempotent, same four steps in both:

1. Create `.venv` if absent (`python -m venv .venv`).
2. Activate and `pip install -r requirements.txt` (quiet; skip when already satisfied).
3. Sanity-check: imports succeed and the configured default fonts exist — print an actionable
   message and exit non-zero otherwise.
4. Start Flask on the host/port from `config/app.conf` and print the URL to open.

`run.sh`: `#!/usr/bin/env bash`, `set -euo pipefail`, committed executable. Neither script may
hardcode an absolute path — resolve everything relative to the script's own directory.

---

## 11. Acceptance criteria

Verified as built. The one box left open needs a printer and a ruler, which no test can substitute.

- [x] `run.bat` on a clean Windows box (Python 3.11+ only) brings the app up with zero manual steps.
- [x] `/` shows both language cards; both links resolve.
- [x] `letters = dashed`, `outlined`, `solid` are **visibly different** in the PDF; `solid` letters
      have hollow counters (the middle of `o` and `a` is white, not filled).
- [x] Changing `letter_thickness` 0.4 → 1.6 pt visibly thickens outlined/dashed strokes; the control
      is disabled for `solid`.
- [x] `letter_darkness` 10 % is a faint trace, 100 % is solid black; same for `guide_darkness`.
- [x] Hindi: `कि`, `की`, `क्ष`, `त्र`, `हिंदी` are **correctly shaped** — matra on the correct side,
      conjuncts ligated. Most important check; verify by eye on a real PDF.
- [x] Hindi shiro-rekha sits **on** the letters' headline, not floating above it.
- [x] English `four-line` setup: lowercase sits on the base line, `t`/`d` reach the top line, `g`
      drops to the descender line when it is enabled.
- [x] A 200-character input line **wraps** instead of running off the page; a blank input line
      produces a blank ruled row.
- [x] `following_lines = blank` leaves rows 2..n ruled and empty; `repeat` fills them.
- [x] `line_spacing = double` clearly increases the gap between rows.
- [x] A full 5,000-character input paginates into many pages with no clipped rows or half-drawn
      guides, and generates in a few seconds (~0.8 s, 24 pages, ~550 KB).
- [x] `paper_size` × `orientation` all four combinations produce correctly sized pages.
- [x] Empty and over-limit text both re-render the form with a readable error, HTTP 400.
- [ ] **Printed at 100 % scale on A4, `line_height = 12 mm` measures 12 mm with a ruler.**
      Correct in the PDF geometry and asserted in tests; still worth checking once on your printer,
      because "fit to page" scaling in the print dialog will silently shrink it.
- [x] Re-generating returns the form with all previous selections intact.
- [x] `pytest` green: 66 tests covering spec clamping, wrap/pagination maths, guide metrics, the
      paint operators per letter style, glyph-form reuse and BBox safety, Devanagari shaping, and a
      render test asserting `%PDF` magic bytes plus page counts via `pypdf`.
- [x] `AGENTS.md` records run/test commands and the shaping pipeline.

---

## 12. Non-goals (Phase 2 backlog)

Not now, but don't design them out: stroke-direction arrows and numbered stroke order, fading
repetitions across a block, cursive/joined script, other scripts (Tamil etc.), accounts, saved
worksheet history, colour guide lines, clipart, hosting/Docker.

---

## 13. Copy-paste build prompt

> Build the `writing_practice` project exactly as specified in `PROMPT.md` in this repository.
> Read the whole file first, especially §4.
>
> Restated constraints: Python 3.11+; runtime deps are **only** Flask, reportlab, uharfbuzz and
> fonttools. Worksheets are **vector** PDFs — text is shaped with uharfbuzz, glyph outlines are
> extracted with fontTools via a `BasePen` subclass, cached per glyph id, and painted onto a
> ReportLab canvas as paths so that `solid` (fill), `outlined` (stroke) and `dashed`
> (stroke + `setDash`) letters plus `letter_thickness` and `letter_darkness` all work. Do **not**
> use Pillow text, WeasyPrint, or `canvas.drawString()` for the worksheet content. Line wrapping
> must use real shaped advance widths. Blank input lines must produce blank ruled rows. Preserve the
> URLs `/english/writing/handwriting/print-practice` and `/hindi/...`; pages 2 and 3 share one Jinja
> template. Every tunable lives in `config/app.conf` with an in-code default. `run.bat` / `run.sh`
> bootstrap the venv, install pinned deps, check fonts, and start the server. Fonts are bundled
> locally with their OFL licenses, never fetched at runtime.
>
> Order of work: (1) skeleton, config, run scripts; (2) `WorksheetSpec` + validation/clamping +
> tests; (3) shaping → outline → paint pipeline, proven on English with all three letter styles;
> (4) guides and vertical metrics; (5) wrapping and pagination with tests; (6) Hindi shaping and
> shiro-rekha placement; (7) routes, templates, CSS with full option round-trip; (8) presets;
> (9) full test pass plus a manual PDF review against the §11 checklist.
>
> Stop and ask before adding any dependency not listed in §9.
