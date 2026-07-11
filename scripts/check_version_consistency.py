#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fail if the VERSION file and pyproject.toml disagree.

PHOTO-CAT keeps its version in two places: the ``VERSION`` file read at runtime by
``photo_cat.__init__`` and ``[tool.poetry].version`` used to build the package.
This guard runs in CI so the two can never silently drift before a release.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
VERSION_FILE = PROJECT_DIR / "VERSION"
PYPROJECT_FILE = PROJECT_DIR / "pyproject.toml"


def read_version_file() -> str:
    """Return the trimmed contents of the VERSION file."""
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def read_pyproject_version() -> str:
    """Return ``[tool.poetry].version`` without requiring a TOML parser on 3.10."""
    text = PYPROJECT_FILE.read_text(encoding="utf-8")

    try:
        import tomllib

        return str(tomllib.loads(text)["tool"]["poetry"]["version"]).strip()
    except ModuleNotFoundError:
        # Python 3.10 has no tomllib; read the first version under [tool.poetry].
        match = re.search(r'(?ms)^\[tool\.poetry\][^\[]*?^version\s*=\s*"([^"]+)"', text)
        if (match is None):
            raise SystemExit("ERROR: could not find [tool.poetry].version in pyproject.toml")
        return match.group(1).strip()


def main() -> int:
    """Compare both version sources and report a stable, explicit CI failure."""
    version_file = read_version_file()
    pyproject_version = read_pyproject_version()

    if (version_file != pyproject_version):
        print(
            f"ERROR: VERSION ({version_file}) does not match "
            f"pyproject.toml [tool.poetry].version ({pyproject_version}).",
            file=sys.stderr,
        )
        print("Set both to the same value before releasing.", file=sys.stderr)
        return 1

    print(f"Version consistent: {version_file}")
    return 0


if (__name__ == "__main__"):
    raise SystemExit(main())
