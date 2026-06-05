# SPDX-License-Identifier: GPL-3.0-only
"""PHOTO-CAT package."""

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
VERSION_FILE = PROJECT_DIR / "VERSION"

try:
    __version__ = VERSION_FILE.read_text(encoding="utf-8", errors="replace").strip() or "unknown"
except Exception:
    __version__ = "unknown"
