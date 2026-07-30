# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Load transmission curves for built-in and user-supplied filters.

One format serves both the built-in library and files the user provides, so the
GUI can state a single requirement. A filter file is two whitespace- or
comma-separated columns::

    wavelength   transmission

Optional header comments declare the units explicitly::

    # unit: nm | angstrom | micron
    # transmission: fraction | percent

When the headers are absent both are auto-detected from the data and normalised:
wavelength to nanometres, transmission to a 0-1 fraction. Detection is a documented
heuristic; the headers remove any ambiguity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..index_manifest import sha256_file

# Wavelength unit -> nanometres.
_UNIT_TO_NM = {
    "nm": 1.0,
    "nanometer": 1.0,
    "nanometre": 1.0,
    "angstrom": 0.1,
    "a": 0.1,
    "aa": 0.1,
    "micron": 1000.0,
    "um": 1000.0,
    "micrometer": 1000.0,
    "micrometre": 1000.0,
}

_HEADER_RE = re.compile(r"^\s*#\s*(unit|transmission|provenance)\s*[:=]\s*(\S+)", re.IGNORECASE)


@dataclass(frozen=True)
class FilterCurve:
    """A transmission curve on a sorted nanometre grid, throughput in [0, 1]."""

    name: str
    wavelength_nm: np.ndarray
    throughput: np.ndarray
    path: str
    sha256: str
    provenance: str = "unspecified"

    @property
    def is_nominal(self) -> bool:
        """Return whether this is a nominal placeholder rather than a measured curve."""
        return self.provenance.startswith("nominal")

    def metadata(self) -> dict[str, object]:
        """Return a JSON-safe description for reproducibility sidecars."""
        return {
            "name": self.name,
            "path": self.path,
            "sha256": self.sha256,
            "provenance": self.provenance,
            "wavelength_min_nm": round(float(self.wavelength_nm[0]), 4),
            "wavelength_max_nm": round(float(self.wavelength_nm[-1]), 4),
            "points": int(self.wavelength_nm.size),
        }


def _read_headers(text: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if (stripped == "" or not stripped.startswith("#")):
            if (stripped != "" and not stripped.startswith("#")):
                break  # first data row: stop scanning for headers
            continue
        match = _HEADER_RE.match(stripped)
        if (match):
            headers[match.group(1).lower()] = match.group(2).strip().lower()
    return headers


def _detect_wavelength_scale(values: np.ndarray) -> float:
    """Return the nanometre scale factor inferred from the wavelength magnitude."""
    peak = float(np.nanmax(values))
    if (peak < 100.0):
        return _UNIT_TO_NM["micron"]
    if (peak < 3000.0):
        return _UNIT_TO_NM["nm"]
    return _UNIT_TO_NM["angstrom"]


def load_filter(path: str | Path, name: str | None = None) -> FilterCurve:
    """Load and normalise one transmission curve to (nm, fraction)."""
    filter_path = Path(path).resolve()
    try:
        text = filter_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"Could not read filter transmission file: {filter_path}") from error

    headers = _read_headers(text)
    rows: list[tuple[float, float]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if (stripped == "" or stripped.startswith("#")):
            continue
        parts = re.split(r"[\s,]+", stripped)
        if (len(parts) < 2):
            raise ValueError(
                f"Filter file must have two columns 'wavelength transmission': {filter_path}"
            )
        try:
            rows.append((float(parts[0]), float(parts[1])))
        except ValueError as error:
            raise ValueError(f"Non-numeric value in filter file {filter_path}: {stripped!r}") from error

    if (len(rows) < 2):
        raise ValueError(f"Filter file must contain at least two rows: {filter_path}")

    data = np.asarray(rows, dtype=np.float64)
    wavelength = data[:, 0]
    throughput = data[:, 1]
    finite = np.isfinite(wavelength) & np.isfinite(throughput)
    wavelength = wavelength[finite]
    throughput = throughput[finite]
    if (wavelength.size < 2):
        raise ValueError(f"Filter file has fewer than two valid rows: {filter_path}")

    unit = headers.get("unit")
    if (unit is not None):
        if (unit not in _UNIT_TO_NM):
            raise ValueError(f"Unknown filter wavelength unit '{unit}' in {filter_path}.")
        scale = _UNIT_TO_NM[unit]
    else:
        scale = _detect_wavelength_scale(wavelength)
    wavelength_nm = wavelength * scale

    scale_hint = headers.get("transmission")
    if (scale_hint == "percent"):
        throughput = throughput / 100.0
    elif (scale_hint == "fraction"):
        pass
    elif (float(np.nanmax(throughput)) > 1.5):
        # No header and values exceed unity: the curve is expressed as a percentage.
        throughput = throughput / 100.0
    throughput = np.clip(throughput, 0.0, 1.0)

    order = np.argsort(wavelength_nm, kind="stable")
    wavelength_nm = wavelength_nm[order]
    throughput = throughput[order]
    unique = np.concatenate(([True], np.diff(wavelength_nm) > 0.0))
    wavelength_nm = wavelength_nm[unique]
    throughput = throughput[unique]
    if (wavelength_nm.size < 2):
        raise ValueError(f"Filter file has fewer than two distinct wavelengths: {filter_path}")
    if (not np.any(throughput > 0.0)):
        raise ValueError(f"Filter file has no positive transmission: {filter_path}")

    return FilterCurve(
        name=(name or filter_path.stem),
        wavelength_nm=wavelength_nm,
        throughput=throughput,
        path=str(filter_path),
        sha256=sha256_file(filter_path),
        provenance=headers.get("provenance", "unspecified"),
    )
