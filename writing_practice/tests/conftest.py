from pathlib import Path

import pytest

from app import create_app
from app.config import load_settings
from app.render.fonts import load_font

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = PROJECT_ROOT / "app" / "static" / "fonts"
ENGLISH_FONT = FONTS_DIR / "Andika-Regular.ttf"
HINDI_FONT = FONTS_DIR / "NotoSansDevanagari-Regular.ttf"


@pytest.fixture(scope="session")
def settings():
    return load_settings(PROJECT_ROOT / "config" / "app.conf")


@pytest.fixture(scope="session")
def english_font():
    return load_font(ENGLISH_FONT)


@pytest.fixture(scope="session")
def hindi_font():
    return load_font(HINDI_FONT)


@pytest.fixture()
def client(settings):
    app = create_app(settings)
    app.config.update(TESTING=True)
    return app.test_client()
