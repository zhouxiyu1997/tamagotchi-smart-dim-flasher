#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -r requirements.txt

echo "Starting DiM web UI with root privileges for flashrom / CH341A access..."
exec sudo "$SCRIPT_DIR/.venv/bin/python" -m dim_tool
