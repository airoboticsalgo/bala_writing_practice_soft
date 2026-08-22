"""Flask application factory."""

from __future__ import annotations

import logging

from flask import Flask

from .config import Settings, load_settings
from .render import fonts as font_lib


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    app.config["SETTINGS"] = settings or load_settings()
    settings = app.config["SETTINGS"]

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for note in font_lib.check_startup(
        settings.path("fonts", "fonts_dir"),
        settings.get("fonts", "english_default"),
        settings.get("fonts", "hindi_default"),
    ):
        app.logger.info("font %s", note)

    from .routes.home import bp as home_bp
    from .routes.practice import bp as practice_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(practice_bp)
    return app
