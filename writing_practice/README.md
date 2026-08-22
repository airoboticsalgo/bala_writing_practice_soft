# writing_practice

Printable handwriting worksheets for **English print** and **Hindi (Devanagari) print**, generated
as vector PDFs. Runs locally: type the text, choose how the letters and guide lines should look,
get a PDF ready to print.

Built to the specification in [PROMPT.md](PROMPT.md).

## Running it

Windows:

```
run.bat
```

Linux / macOS:

```
./run.sh
```

Either script creates `.venv`, installs the pinned dependencies, checks the bundled fonts, and
starts the server at <http://127.0.0.1:5000/>. Requires Python 3.11+ and nothing else — no GTK, no
headless browser, no system font packages.

## Pages

| URL | What it does |
|---|---|
| `/` | Pick a language |
| `/english/writing/handwriting/print-practice` | English worksheet builder |
| `/hindi/writing/handwriting/print-practice` | Hindi worksheet builder |

The worksheet opens in a new tab as a PDF; print it at **100 % scale** (not "fit to page") or the
line heights will not measure correctly.

## Options

**Content** — page title, optional instructions line, up to 5,000 characters of text, presets
(A–Z, CVC words, sight words / स्वर, व्यंजन, मात्राएँ, बारहखड़ी, अंक, simple words), letter case
(English), name and date lines.

**Guide lines** — the base line is always drawn. Optionally: top (ascender) line, dashed middle
(x-height) line and descender line for English; shiro-rekha, upper matra line and lower matra line
for Hindi. Line height 8–25 mm, plus guide darkness and thickness (0.15–2 pt). Line style is
`classic` (solid rules, aiming lines dashed) or forced to all-`solid`, all-`dashed` or all-`dotted`,
the base line included.

**Letters** — `dashed` (trace over the dashes), `dotted` (trace dot to dot), `outlined` (hollow,
trace or colour in) or `solid` (a model to copy), with adjustable darkness. Thickness (0.2–2.5 pt)
sets the stroke width of the three traceable styles, and doubles as the dot size for `dotted`.
Dash & dot spacing is `tight`, `normal` or `wide`. Solid is `single` (flat fill) or `double`
(filled with an outline of `solid_weight` 0–1.2 pt); 0 pt keeps the letter at its true outline.

**Lines & repetition** — single or double line spacing, 1–20 lines per page, and whether the
following lines repeat the text or are left blank.

**Layout** — A4 or Letter, tall or wide.

Each input line becomes one writing line. Lines too long to fit **wrap**, measured from real shaped
glyph widths. A **blank input line produces a blank ruled row** — deliberate free-practice space.

Defaults live in [`config/app.conf`](config/app.conf); every key has an in-code fallback, so a
missing or partial file still boots. Point `WRITING_PRACTICE_CONFIG` elsewhere to use another file.

## How it renders (and why it is built this way)

Devanagari cannot be drawn by mapping characters to glyphs one at a time: matras reorder visually
(`कि` is typed क + ि but drawn ि first) and conjuncts ligate (`क्ष`, `त्र`). Dashed and outlined
letters additionally need the glyph *outline*, since you cannot dash or variable-stroke a rasterised
letter. So:

1. **uharfbuzz** shapes the text — correct reordering, ligatures, and the advance widths used for
   line wrapping.
2. **fontTools** extracts each glyph's outline through a `BasePen` subclass, which resolves
   composite glyphs and converts TrueType quadratics to cubics. Outlines are cached per glyph.
3. **reportlab** paints the paths: fill for `solid` (non-zero winding, so counters stay hollow),
   stroke for `outlined`, stroke plus a PDF dash array for `dashed` — dashes follow beziers
   natively — and for `dotted` a *zero-length* dash under a round line cap, which PDF paints as a
   row of circles the width of the line.
4. Each distinct glyph is emitted **once** as a Form XObject and then invoked with a translate/scale
   matrix, the same trick embedded fonts use. A 5,000-character worksheet is ~0.8 s and ~550 KB
   instead of ~4.5 s and ~5 MB.

Guide positions are measured from **ink**, not font metric tables: the top line is the top of `b`,
the middle line the top of `x`, and the shiro-rekha the top of a bare `क`. Andika reports an `hhea`
ascender of 2500 on a 2048 em because it includes line gap, so trusting the table would render
"12 mm letters" at 6.7 mm and float the Hindi headline above the letters.

## Fonts

Bundled in `app/static/fonts/`, all OFL, with their licenses:

- **Andika** (SIL) — English default; built for literacy teaching, single-storey `a` and `g`
- **ABeeZee** — English alternative
- **Noto Sans Devanagari** — Hindi default; a static instance of the variable font
- **Mukta** — Hindi alternative

If you also copy the Lucida faces from a Windows install, the English page lists:

- **Lucida Handwriting** (connected cursive)
- **Lucida Sans** and **Lucida Sans Italic** (disconnected, slanted print — closest to the
  "Lucida Handwriting" disconnected look)
- **Lucida Sans Demibold** / **Lucida Sans Demibold Italic**
- **Lucida Sans Typewriter**

Optionally, the Lucida faces that ship with Windows can be used for English. They are **not** OFL,
so they are gitignored rather than bundled; copy them in from your own Windows install:

```
copy C:\Windows\Fonts\LHANDW.TTF app\static\fonts\LucidaHandwriting-Regular.ttf
copy C:\Windows\Fonts\LSANS.TTF  app\static\fonts\LucidaSans-Regular.ttf
copy C:\Windows\Fonts\LTYPE.TTF  app\static\fonts\LucidaSansTypewriter-Regular.ttf
```

Nothing is downloaded at runtime. The font dropdown lists only fonts on disk that can actually
render the page's script.

## Tests

```
.venv\Scripts\python -m pytest        # Windows
.venv/bin/python -m pytest            # Linux / macOS
```

Covers input clamping, wrapping and pagination arithmetic, the PDF paint operators for each letter
style, glyph-form reuse and BBox safety, guide metrics, and — most importantly — that Devanagari is
genuinely shaped rather than mapped.

## Not built (yet)

Stroke-direction arrows and numbered stroke order, cursive/joined script, other scripts, accounts,
saved worksheet history, colour guide lines, clipart.
