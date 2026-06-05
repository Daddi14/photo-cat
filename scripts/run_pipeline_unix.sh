#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

export PHOTO_CAT_COMPACT_LOG="1"
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_EXE="./.venv/bin/python"
if [ ! -x "$PYTHON_EXE" ]; then
    echo
    echo "ERROR: the local virtual environment was not found."
    echo "Run sh START_UNIX.sh first so PHOTO-CAT can create .venv and install libraries."
    echo
    printf "Press Enter to close this window..."
    read -r _
    exit 1
fi

"$PYTHON_EXE" -m photo_cat.config_and_run
STATUS=$?

echo
printf "Press Enter to close this window..."
read -r _
exit "$STATUS"
