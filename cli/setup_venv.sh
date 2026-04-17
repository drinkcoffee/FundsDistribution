#!/usr/bin/env bash
# Create and populate the virtual environment for fundsdist.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "Virtual environment created at $VENV_DIR"
echo "Activate it with:  source .venv/bin/activate"
echo "Then run:          python fundsdist.py"
