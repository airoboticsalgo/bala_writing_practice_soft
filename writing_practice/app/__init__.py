"""Flask application factory."""

from __future__ import annotations

import logging
import os

from flask import Flask, redirect, request, url_for

from .auth import is_logged_in
from .config import Settings, load_settings
from .render import fonts as font_lib


def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("WRITING_PRACTICE_SECRET") or os.urandom(24)
    app.config["SETTINGS"] = settings or load_settings()
    settings = app.config["SETTINGS"]

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for note in font_lib.check_startup(
        settings.path("fonts", "fonts_dir"),
        settings.get("fonts", "english_default"),
        settings.get("fonts", "hindi_default"),
    ):
        app.logger.info("font %s", note)

    from .routes.auth import bp as auth_bp
    from .routes.home import bp as home_bp
    from .routes.practice import bp as practice_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(practice_bp)

    @app.before_request
    def require_login():
        if is_logged_in() or app.config.get("TESTING"):
            return None
        if request.endpoint in ("auth.login", "auth.logout", "static"):
            return None
        return redirect(url_for("auth.login"))

    return app
