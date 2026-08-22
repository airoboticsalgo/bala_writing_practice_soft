"""Entry point: ``python wsgi.py`` (or point a WSGI server at ``app``)."""

from app import create_app
from app.config import load_settings

settings = load_settings()
app = create_app(settings)


if __name__ == "__main__":
    host = settings.get("server", "host")
    port = settings.int("server", "port")
    print(f" * Writing Practice ready at http://{host}:{port}/")
    app.run(host=host, port=port, debug=settings.bool("server", "debug"))
