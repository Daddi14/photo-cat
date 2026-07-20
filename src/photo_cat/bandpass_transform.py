# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Validated empirical colour transformations from catalogue to mission bands."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from .index_manifest import sha256_file


BANDPASS_PROFILE_SCHEMA_VERSION = 1
STATUS_MISSING_INPUT = 0
STATUS_VALID = 1
STATUS_OUTSIDE_VALIDITY = 2
STATUS_EXTRAPOLATED = 3
STATUS_NAMES = {
    STATUS_MISSING_INPUT: "missing_input",
    STATUS_VALID: "valid",
    STATUS_OUTSIDE_VALIDITY: "outside_validity",
    STATUS_EXTRAPOLATED: "extrapolated",
}


@dataclass(frozen=True)
class BandpassTransformProfile:
    """One provenance-bearing empirical colour-polynomial transformation."""

    name: str
    output_band: str
    base_band: str
    color_band_1: str
    color_band_2: str
    coefficients: tuple[float, ...]
    color_min: float | None
    color_max: float | None
    base_magnitude_min: float | None
    base_magnitude_max: float | None
    out_of_range: str
    reference: str
    profile_path: str
    profile_sha256: str

    @property
    def required_bands(self) -> tuple[str, ...]:
        """Return unique catalogue bands needed to evaluate the profile."""
        return tuple(dict.fromkeys((self.base_band, self.color_band_1, self.color_band_2)))

    def metadata(self) -> dict[str, Any]:
        """Return a JSON-safe profile description for reproducibility sidecars."""
        payload = asdict(self)
        payload["coefficients"] = list(self.coefficients)
        payload["required_bands"] = list(self.required_bands)
        return payload


@dataclass(frozen=True)
class BandpassTransformResult:
    """Transformed magnitudes and per-source validity status codes."""

    magnitudes: np.ndarray
    status_codes: np.ndarray


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if (not isinstance(value, dict)):
        raise ValueError(f"{label} must be a YAML mapping.")
    return value


def _text(value: Any, label: str) -> str:
    text = "" if value is None else str(value).strip()
    if (text == ""):
        raise ValueError(f"{label} cannot be empty.")
    return text


def _optional_finite(value: Any, label: str) -> float | None:
    if (value is None):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a finite number or null.") from error
    if (not math.isfinite(result)):
        raise ValueError(f"{label} must be a finite number or null.")
    return result


def load_bandpass_profile(path: str | Path) -> BandpassTransformProfile:
    """Load and validate one schema-versioned YAML transformation profile."""
    profile_path = Path(path).resolve()
    try:
        payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"Could not read bandpass transformation profile: {profile_path}") from error
    except yaml.YAMLError as error:
        raise ValueError(f"Bandpass transformation profile contains invalid YAML: {profile_path}") from error
    document = _mapping(payload, "Bandpass transformation profile")
    if (document.get("schema_version") != BANDPASS_PROFILE_SCHEMA_VERSION):
        raise ValueError(f"Bandpass transformation profile schema_version must be {BANDPASS_PROFILE_SCHEMA_VERSION}.")

    color_bands = document.get("color_bands")
    if (not isinstance(color_bands, list) or len(color_bands) != 2):
        raise ValueError("Bandpass transformation color_bands must contain exactly two band names.")
    raw_coefficients = document.get("coefficients")
    if (not isinstance(raw_coefficients, list) or not raw_coefficients):
        raise ValueError("Bandpass transformation coefficients must be a non-empty list.")
    coefficients = tuple(_optional_finite(value, "coefficients[]") for value in raw_coefficients)
    if (any(value is None for value in coefficients)):
        raise ValueError("Bandpass transformation coefficients cannot contain null values.")

    validity = _mapping(document.get("validity", {}), "Bandpass transformation validity")
    color_min = _optional_finite(validity.get("color_min"), "validity.color_min")
    color_max = _optional_finite(validity.get("color_max"), "validity.color_max")
    magnitude_min = _optional_finite(validity.get("base_magnitude_min"), "validity.base_magnitude_min")
    magnitude_max = _optional_finite(validity.get("base_magnitude_max"), "validity.base_magnitude_max")
    if (color_min is not None and color_max is not None and color_min > color_max):
        raise ValueError("validity.color_min cannot exceed validity.color_max.")
    if (magnitude_min is not None and magnitude_max is not None and magnitude_min > magnitude_max):
        raise ValueError("validity.base_magnitude_min cannot exceed validity.base_magnitude_max.")
    raw_out_of_range = document.get("out_of_range", "null")
    out_of_range = "null" if raw_out_of_range is None else str(raw_out_of_range).strip().lower()
    if (out_of_range not in {"null", "extrapolate"}):
        raise ValueError("Bandpass transformation out_of_range must be null or extrapolate.")

    return BandpassTransformProfile(
        name=_text(document.get("name"), "name"),
        output_band=_text(document.get("output_band"), "output_band"),
        base_band=_text(document.get("base_band"), "base_band"),
        color_band_1=_text(color_bands[0], "color_bands[0]"),
        color_band_2=_text(color_bands[1], "color_bands[1]"),
        coefficients=tuple(float(value) for value in coefficients if value is not None),
        color_min=color_min,
        color_max=color_max,
        base_magnitude_min=magnitude_min,
        base_magnitude_max=magnitude_max,
        out_of_range=out_of_range,
        reference=str(document.get("reference", "")).strip(),
        profile_path=str(profile_path),
        profile_sha256=sha256_file(profile_path),
    )


def transform_magnitudes(
    profile: BandpassTransformProfile,
    magnitude_arrays: dict[str, np.ndarray],
) -> BandpassTransformResult:
    """Apply ``m_out = m_base + sum(c_i * colour**i)`` with validity tracking."""
    missing = [band for band in profile.required_bands if band not in magnitude_arrays]
    if (missing):
        raise ValueError(f"Bandpass transformation requires unavailable magnitude bands: {', '.join(missing)}")
    base = np.asarray(magnitude_arrays[profile.base_band], dtype=np.float64)
    first = np.asarray(magnitude_arrays[profile.color_band_1], dtype=np.float64)
    second = np.asarray(magnitude_arrays[profile.color_band_2], dtype=np.float64)
    if (first.shape != base.shape or second.shape != base.shape or base.ndim != 1):
        raise ValueError("Bandpass transformation magnitude arrays must be aligned one-dimensional arrays.")

    color = first - second
    finite = np.isfinite(base) & np.isfinite(first) & np.isfinite(second)
    in_range = finite.copy()
    if (profile.color_min is not None):
        in_range &= color >= profile.color_min
    if (profile.color_max is not None):
        in_range &= color <= profile.color_max
    if (profile.base_magnitude_min is not None):
        in_range &= base >= profile.base_magnitude_min
    if (profile.base_magnitude_max is not None):
        in_range &= base <= profile.base_magnitude_max

    correction = np.polynomial.polynomial.polyval(color, profile.coefficients)
    transformed = base + correction
    status = np.full(base.shape, STATUS_MISSING_INPUT, dtype=np.uint8)
    status[in_range] = STATUS_VALID
    outside = finite & ~in_range
    if (profile.out_of_range == "extrapolate"):
        status[outside] = STATUS_EXTRAPOLATED
    else:
        transformed[outside] = np.nan
        status[outside] = STATUS_OUTSIDE_VALIDITY
    transformed[~finite] = np.nan
    return BandpassTransformResult(np.asarray(transformed, dtype=np.float64), status)


def transform_status_name(status_codes: np.ndarray, index: int) -> str:
    """Return the stable public status name for one catalogue row."""
    if (index < 0 or index >= status_codes.shape[0]):
        return "missing_input"
    return STATUS_NAMES.get(int(status_codes[index]), "missing_input")
