# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Discover the mission filters available to PHOTO-CAT.

Filters are addressed by a normalised key such as ``gaia_bp`` (from
``Gaia/BP.dat``) or ``tess`` (from ``TESS/response.dat``), and come from two
directories that are scanned together at call time, so adding a mission is just
dropping a correctly formatted file in a new folder: no code change.

- The **shipped** library inside the package holds the official curves that ride
  along with the release. It belongs to the installation and is replaced whenever
  the package is upgraded or reinstalled.
- The **user** library lives in the per-user data directory. Filters downloaded
  from SVO and curves the user adds go here, so that reinstalling or upgrading
  PHOTO-CAT (``pip install --upgrade``, ``pipx upgrade``, a rebuilt virtual
  environment) cannot discard them along with the package.

Both are scanned, so a filter that predates this split and still sits inside the
package keeps working. On a key collision the user library wins, which is what
lets a locally installed curve replace a shipped one; the resolved path and its
checksum are recorded in the run metadata, so which curve was used stays visible.
"""

from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from .filters import FilterCurve, load_filter

FILTERS_ROOT = Path(__file__).resolve().parent.parent / "filters"

# Points the writable library somewhere else. Used by the test suite so a
# developer's own downloaded filters can never leak into a test run.
USER_FILTERS_DIR_ENV = "PHOTO_CAT_FILTERS_DIR"

# A single-band mission file may be named after the mission or "response"/"band";
# in that case the mission name alone also addresses it (output_band: TESS).
_MISSION_ALIAS_STEMS = {"response", "band", "filter", "throughput"}


def _platform_data_dir() -> Path:
    """Return the per-user data directory for the current platform."""
    if (sys.platform == "win32"):
        return Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    if (sys.platform == "darwin"):
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))


def user_filters_root() -> Path:
    """Return the writable directory downloaded and user-added filters live in.

    Read at call time rather than at import, so the environment override applies
    to a process that sets it after PHOTO-CAT is imported. The directory is
    created on demand by whatever writes into it, not here.
    """
    override = os.environ.get(USER_FILTERS_DIR_ENV, "").strip()
    if (override):
        return Path(override).expanduser().resolve()
    return _platform_data_dir() / "photo-cat" / "filters"


def normalized_band_key(value: str) -> str:
    """Return the lowercase alphanumeric key used to address a filter."""
    key = re.sub(r"[^0-9a-z]+", "_", str(value).strip().lower()).strip("_")
    if (key == ""):
        raise ValueError("Filter band names cannot be empty.")
    return key


def _collect_into(root: Path, mapping: dict[str, str]) -> None:
    """Add every filter under one root to the mapping, keeping earlier entries."""
    if (not root.is_dir()):
        return
    for filter_file in sorted(root.glob("*/*.dat")):
        mission = normalized_band_key(filter_file.parent.name)
        stem = normalized_band_key(filter_file.stem)
        mapping.setdefault(f"{mission}_{stem}", str(filter_file))
        if (stem in _MISSION_ALIAS_STEMS or stem == mission):
            mapping.setdefault(mission, str(filter_file))


@lru_cache(maxsize=1)
def _discover(user_root_marker: str, shipped_root_marker: str) -> dict[str, str]:
    """Return a mapping of band key -> filter file path across both libraries.

    The roots are passed as resolved strings, so the cache follows the actual
    directories rather than being pinned to the first call in a test that patches
    them. The user root is scanned first and ``setdefault`` keeps the first entry,
    which is how a locally installed curve takes precedence over a shipped one.
    """
    mapping: dict[str, str] = {}
    _collect_into(Path(user_root_marker), mapping)
    _collect_into(Path(shipped_root_marker), mapping)
    return mapping


def _library() -> dict[str, str]:
    return _discover(str(user_filters_root()), str(FILTERS_ROOT))


def available_output_bands() -> list[str]:
    """Return the sorted band keys installed in the built-in filter library."""
    return sorted(_library())


def library_filter_path(band: str) -> str | None:
    """Return the installed filter file for a band key, or None when absent."""
    return _library().get(normalized_band_key(band))


def load_library_filter(band: str) -> FilterCurve:
    """Load a built-in filter by band key, with an actionable error when missing."""
    path = library_filter_path(band)
    if (path is None):
        available = ", ".join(available_output_bands()) or "(none installed)"
        raise ValueError(
            f"No installed filter found for band '{band}'. Installed bands: {available}. "
            f"Add its official transmission curve as {user_filters_root()}/<Mission>/<band>.dat, "
            "download it from SVO in the configurator, or pass a custom filter file."
        )
    return load_filter(path, name=normalized_band_key(band))


def resolve_output_filter(output_band: str, filter_file: str | None) -> FilterCurve:
    """Resolve the requested output band to a loaded filter curve.

    ``output_band == "custom"`` loads ``filter_file``; anything else is looked up in
    the built-in library.
    """
    if (normalized_band_key(output_band) == "custom"):
        if (filter_file is None):
            raise ValueError("output_band 'custom' requires a filter_file with the transmission curve.")
        return load_filter(filter_file, name="custom")
    return load_library_filter(output_band)
