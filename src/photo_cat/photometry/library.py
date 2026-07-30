# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Discover built-in mission filters shipped with PHOTO-CAT.

Filters live under ``photo_cat/filters/<Mission>/<band>.dat``. The tree is scanned
at call time, so adding a mission is just dropping a correctly formatted file in a
new folder: no code change. A band is addressed by a normalised key such as
``gaia_bp`` (from ``Gaia/BP.dat``) or ``tess`` (from ``TESS/response.dat``).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .filters import FilterCurve, load_filter

FILTERS_ROOT = Path(__file__).resolve().parent.parent / "filters"

# A single-band mission file may be named after the mission or "response"/"band";
# in that case the mission name alone also addresses it (output_band: TESS).
_MISSION_ALIAS_STEMS = {"response", "band", "filter", "throughput"}


def normalized_band_key(value: str) -> str:
    """Return the lowercase alphanumeric key used to address a filter."""
    key = re.sub(r"[^0-9a-z]+", "_", str(value).strip().lower()).strip("_")
    if (key == ""):
        raise ValueError("Filter band names cannot be empty.")
    return key


@lru_cache(maxsize=1)
def _discover(root_marker: str) -> dict[str, str]:
    """Return a mapping of band key -> filter file path under the library root.

    ``root_marker`` is the resolved root string, so the cache follows the actual
    directory rather than being pinned to the first call in a test that patches it.
    """
    mapping: dict[str, str] = {}
    root = Path(root_marker)
    if (not root.is_dir()):
        return mapping
    for filter_file in sorted(root.glob("*/*.dat")):
        mission = normalized_band_key(filter_file.parent.name)
        stem = normalized_band_key(filter_file.stem)
        mapping.setdefault(f"{mission}_{stem}", str(filter_file))
        if (stem in _MISSION_ALIAS_STEMS or stem == mission):
            mapping.setdefault(mission, str(filter_file))
    return mapping


def _library() -> dict[str, str]:
    return _discover(str(FILTERS_ROOT))


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
            f"No built-in filter found for band '{band}'. Installed bands: {available}. "
            f"Add its official transmission curve as {FILTERS_ROOT}/<Mission>/<band>.dat, "
            "or pass a custom filter file."
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
