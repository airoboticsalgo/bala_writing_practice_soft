#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PY=".venv/bin/python"

if [ ! -x "$PY" ]; then
    echo "No .venv found. Run ./run.sh first to set up the environment."
    exit 1
fi

if ! "$PY" -m gunicorn --version >/dev/null 2>&1; then
    echo "gunicorn is not installed in .venv."
    echo "Install it with: $PY -m pip install gunicorn"
    exit 1
fi

# Bind 0.0.0.0 (public) on the configured port. 127.0.0.1 is treated as 0.0.0.0
# for a production deployment; set any other IP in config/app.conf if needed.
BIND=$("$PY" - <<'PY'
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import load_settings

settings = load_settings()
host = settings.get("server", "host")
if host == "127.0.0.1":
    host = "0.0.0.0"
port = settings.get("server", "port")
print(f"{host}:{port}")
PY
)

exec "$PY" -m gunicorn -w 4 -b "$BIND" wsgi:app
