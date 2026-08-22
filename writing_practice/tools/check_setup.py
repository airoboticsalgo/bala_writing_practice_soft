"""Pre-flight check used by run.bat / run.sh: imports work and fonts are present."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        import uharfbuzz  # noqa: F401
        import reportlab  # noqa: F401
        from fontTools.ttLib import TTFont  # noqa: F401
    except ImportError as error:
        print(f"ERROR: missing dependency ({error}).", file=sys.stderr)
        print("Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    from app.config import load_settings
    from app.render import fonts as font_lib

    settings = load_settings()
    try:
        notes = font_lib.check_startup(
            settings.path("fonts", "fonts_dir"),
            settings.get("fonts", "english_default"),
            settings.get("fonts", "hindi_default"),
        )
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    for note in notes:
        print(f"  font {note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
