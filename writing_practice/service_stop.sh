#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="writing-practice"

if [ "$EUID" -ne 0 ]; then
  echo "This script must be run as root."
  exit 1
fi

systemctl stop "${SERVICE_NAME}"
echo "Stopped ${SERVICE_NAME}"
