#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$0")" && pwd)}"
SERVICE_NAME="writing-practice"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
VENV_BIN="${PROJECT_DIR}/.venv/bin"

if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root."
  exit 1
fi

if [ ! -x "${VENV_BIN}/python" ]; then
  echo "No .venv found in ${PROJECT_DIR}. Run ./run.sh first."
  exit 1
fi

if ! "${VENV_BIN}/python" -m gunicorn --version >/dev/null 2>&1; then
  echo "Installing gunicorn ..."
  "${VENV_BIN}/python" -m pip install gunicorn
fi

if ! "${VENV_BIN}/python" -m gunicorn --version >/dev/null 2>&1; then
  echo "gunicorn installation failed."
  exit 1
fi

chmod +x "${PROJECT_DIR}/prod_run.sh"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Writing Practice web app
After=network.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
Environment="WRITING_PRACTICE_CONFIG=${PROJECT_DIR}/config/prod.conf"
ExecStart=${PROJECT_DIR}/prod_run.sh
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

chmod 644 "${SERVICE_FILE}"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

echo "Service ${SERVICE_NAME} created and enabled."
echo "Run ./service_start.sh to start it."
