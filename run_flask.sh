#!/bin/bash
# Wrapper: run Flask using system Python 3.9 with venv site-packages on PYTHONPATH.
# This avoids the macOS sandbox restriction on reading venv/pyvenv.cfg.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/venv/lib/python3.9/site-packages"
exec /usr/bin/python3 "$SCRIPT_DIR/app.py" "$@"
