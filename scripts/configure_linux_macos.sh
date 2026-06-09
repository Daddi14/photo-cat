#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
set -e
cd "$(dirname "$0")/.."
bash scripts/start_linux_macos.sh --configure-only
