#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PY=".venv/bin/python"

if [ ! -x "$PY" ]; then
  echo "Creating virtual environment in .venv ..."
  python3 -m venv .venv
fi

echo "Checking dependencies ..."
"$PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo "Checking fonts ..."
"$PY" -m tools.check_setup

exec "$PY" wsgi.py
