#!/usr/bin/env sh
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if command -v bash >/dev/null 2>&1; then
    exec bash "scripts/start_linux_macos.sh" "$@"
fi

echo "ERROR: bash was not found. Please install bash, then run this again."
exit 1
