# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""PHOTO-CAT package."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
VERSION_FILE = PROJECT_DIR / "VERSION"


def _read_version() -> str:
    """Return the project version from source checkout or installed metadata."""
    try:
        version = VERSION_FILE.read_text(encoding="utf-8", errors="replace").strip()
        if (version):
            return version
    except Exception:
        pass

    try:
        return importlib.metadata.version("photo-cat")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


__version__ = _read_version()
