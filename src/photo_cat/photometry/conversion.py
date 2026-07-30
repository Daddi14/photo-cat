# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Convert catalogue magnitudes into a chosen output band.

Pipeline, per source: colour -> effective temperature -> output/anchor flux ratio
-> output-band magnitude. The heavy synthetic photometry (integrating the SED
through each filter) is done once on a temperature grid at construction; per-source
work is two vectorised ``np.interp`` calls, so converting a whole catalogue is O(N)
and the same cost class as a simple polynomial.

Only flux ratios within one band are ever used downstream, so the output band's
absolute zero-point cancels. The conversion keeps the anchor band's zero-point
(``m_out = m_anchor`` when the flux ratio is 1), which makes every converted
magnitude ratio-safe. The one zero-point that does affect results is the colour
scale, anchored to the Sun so a blackbody's instrumental colour matches the
catalogue's calibrated colour at one physical point.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from .catalogs import CatalogSpec, resolve_catalog
from .filters import FilterCurve, load_filter
from .library import load_library_filter, resolve_output_filter
from .sed import SED_MODELS

# np.trapezoid is the name from NumPy 2.0; NumPy 1.24-1.x only ships np.trapz.
# getattr for both keeps mypy off the version-specific stub attribute.
_trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")

STATUS_MISSING_INPUT = 0
STATUS_VALID = 1
STATUS_CLAMPED = 2
STATUS_NAMES = {
    STATUS_MISSING_INPUT: "missing_input",
    STATUS_VALID: "valid",
    STATUS_CLAMPED: "colour_out_of_grid",
}

# Blackbody-equivalent colour temperature is only meaningful over a stellar range;
# the grid is dense enough that linear interpolation is exact to well under a kelvin.
_TEFF_MIN_K = 2000.0
_TEFF_MAX_K = 50000.0
_TEFF_GRID_POINTS = 400


@dataclass(frozen=True)
class ConversionResult:
    """Output-band magnitudes and per-source temperature and status."""

    out_magnitudes: np.ndarray
    effective_temperature: np.ndarray
    status_codes: np.ndarray
    metadata: dict[str, Any]


def _band_flux_over_teff(
    filter_curve: FilterCurve,
    sed_model: Callable[[np.ndarray, float], np.ndarray],
    teff_grid: np.ndarray,
) -> np.ndarray:
    """Return the SED-weighted throughput integral of one filter at each temperature."""
    wavelength = filter_curve.wavelength_nm
    throughput = filter_curve.throughput
    flux = np.empty(teff_grid.shape, dtype=np.float64)
    for index, teff in enumerate(teff_grid):
        density = sed_model(wavelength, float(teff))
        flux[index] = _trapezoid(density * throughput, wavelength)
    return flux


def _status_name(status_codes: np.ndarray, index: int) -> str:
    """Return the stable public status name for one catalogue row."""
    if (index < 0 or index >= status_codes.shape[0]):
        return "missing_input"
    return STATUS_NAMES.get(int(status_codes[index]), "missing_input")


class PhotometricConverter:
    """Precomputed colour->Teff and Teff->flux-ratio tables for one band conversion."""

    def __init__(
        self,
        catalog: CatalogSpec,
        output_filter: FilterCurve,
        method: str,
        anchor_filter: FilterCurve,
        colour_filter_1: FilterCurve,
        colour_filter_2: FilterCurve,
    ) -> None:
        self.catalog = catalog
        self.output_filter = output_filter
        self.method = method
        self._status_name = _status_name

        sed_model = SED_MODELS[method]
        teff_grid = np.linspace(_TEFF_MIN_K, _TEFF_MAX_K, _TEFF_GRID_POINTS)

        # Integrate each distinct filter over the temperature grid only once, keyed by
        # content hash. When the output band is the same filter as the anchor or a
        # colour band -- the common gaia_g in and gaia_g out case, where the ratio is
        # identically 1 -- its integral is reused instead of recomputed.
        flux_cache: dict[str, np.ndarray] = {}

        def band_flux(filter_curve: FilterCurve) -> np.ndarray:
            cached = flux_cache.get(filter_curve.sha256)
            if (cached is None):
                cached = _band_flux_over_teff(filter_curve, sed_model, teff_grid)
                flux_cache[filter_curve.sha256] = cached
            return cached

        anchor_flux = band_flux(anchor_filter)
        colour_flux_1 = band_flux(colour_filter_1)
        colour_flux_2 = band_flux(colour_filter_2)
        output_flux = band_flux(output_filter)
        self.is_identity = output_filter.sha256 == anchor_filter.sha256

        # Instrumental blackbody colour, then anchored to the catalogue scale so that
        # the Sun's colour maps to the Sun's temperature (removes the zero-point gap
        # between a blackbody's colour and the catalogue's calibrated colour).
        instrumental_colour = -2.5 * np.log10(colour_flux_1 / colour_flux_2)
        solar_instrumental = float(
            np.interp(catalog.solar_teff_kelvin, teff_grid, instrumental_colour)
        )
        colour_zero_point = catalog.solar_colour - solar_instrumental
        observed_colour = instrumental_colour + colour_zero_point

        # colour -> Teff needs colour strictly increasing for np.interp. Blackbody
        # colour decreases with temperature, so ordering by colour reverses Teff.
        order = np.argsort(observed_colour, kind="stable")
        colour_sorted = observed_colour[order]
        strictly_increasing = np.concatenate(([True], np.diff(colour_sorted) > 0.0))
        self._colour_grid = colour_sorted[strictly_increasing]
        self._teff_from_colour = teff_grid[order][strictly_increasing]
        self._colour_min = float(self._colour_grid[0])
        self._colour_max = float(self._colour_grid[-1])

        # Teff -> output/anchor flux ratio, Teff ascending for np.interp.
        self._teff_grid = teff_grid
        self._flux_ratio = output_flux / anchor_flux

        self.metadata: dict[str, Any] = {
            "catalog": catalog.name,
            "output_band": output_filter.name,
            "conversion_method": method,
            "anchor_band": catalog.anchor_band,
            "colour_bands": list(catalog.colour_bands),
            "filter_used": output_filter.metadata(),
            "solar_colour_anchor": catalog.solar_colour,
            "solar_teff_anchor_k": catalog.solar_teff_kelvin,
            "teff_grid_k": [round(_TEFF_MIN_K, 1), round(_TEFF_MAX_K, 1)],
            "colour_grid": [round(self._colour_min, 4), round(self._colour_max, 4)],
        }

    def convert(self, magnitude_arrays: dict[str, np.ndarray]) -> ConversionResult:
        """Convert one aligned set of catalogue magnitude arrays to the output band."""
        spec = self.catalog
        missing = [band for band in spec.required_bands if band not in magnitude_arrays]
        if (missing):
            raise ValueError(
                "Photometric conversion requires magnitude bands absent from the index: "
                f"{', '.join(missing)}. Rebuild the index with these magnitude_columns."
            )

        anchor = np.asarray(magnitude_arrays[spec.anchor_band], dtype=np.float64)
        colour_1 = np.asarray(magnitude_arrays[spec.colour_band_1], dtype=np.float64)
        colour_2 = np.asarray(magnitude_arrays[spec.colour_band_2], dtype=np.float64)
        if (anchor.ndim != 1 or colour_1.shape != anchor.shape or colour_2.shape != anchor.shape):
            raise ValueError("Photometric conversion magnitude arrays must be aligned 1-D arrays.")

        colour = colour_1 - colour_2
        finite = np.isfinite(anchor) & np.isfinite(colour_1) & np.isfinite(colour_2)

        clamped_colour = np.clip(colour, self._colour_min, self._colour_max)
        temperature = np.interp(clamped_colour, self._colour_grid, self._teff_from_colour)
        if (self.is_identity):
            # Output filter == anchor filter: the flux ratio is exactly 1 everywhere,
            # so the converted magnitude is the anchor magnitude. Skip the ratio
            # interpolation and the logarithm entirely.
            out_magnitudes = anchor.copy()
        else:
            flux_ratio = np.interp(temperature, self._teff_grid, self._flux_ratio)
            out_magnitudes = anchor - 2.5 * np.log10(flux_ratio)

        status = np.full(anchor.shape, STATUS_MISSING_INPUT, dtype=np.uint8)
        status[finite] = STATUS_VALID
        out_of_grid = finite & ((colour < self._colour_min) | (colour > self._colour_max))
        status[out_of_grid] = STATUS_CLAMPED

        out_magnitudes = np.where(finite, out_magnitudes, np.nan)
        temperature = np.where(finite, temperature, np.nan)
        return ConversionResult(
            out_magnitudes=np.asarray(out_magnitudes, dtype=np.float64),
            effective_temperature=np.asarray(temperature, dtype=np.float64),
            status_codes=status,
            metadata=self.metadata,
        )


def build_converter(
    catalog: CatalogSpec,
    output_band: str,
    conversion_method: str,
    filter_file: str | None,
) -> PhotometricConverter:
    """Assemble a converter, loading the anchor, colour, and output filters."""
    if (conversion_method not in SED_MODELS):
        supported = ", ".join(SED_MODELS)
        raise ValueError(f"Unknown conversion_method '{conversion_method}'. Supported: {supported}.")

    def catalogue_filter(band: str) -> FilterCurve:
        return load_library_filter(catalog.band_filters.get(band, band))

    output_filter = resolve_output_filter(output_band, filter_file)
    if (output_filter.is_nominal):
        warnings.warn(
            f"Output band '{output_band}' uses a NOMINAL approximate passband, not an "
            "official instrument response. Results are indicative only; install the "
            "official transmission curve for quantitative work.",
            stacklevel=2,
        )
    return PhotometricConverter(
        catalog=catalog,
        output_filter=output_filter,
        method=conversion_method,
        anchor_filter=catalogue_filter(catalog.anchor_band),
        colour_filter_1=catalogue_filter(catalog.colour_band_1),
        colour_filter_2=catalogue_filter(catalog.colour_band_2),
    )


def convert_magnitudes(
    magnitude_arrays: dict[str, np.ndarray],
    output_band: str,
    conversion_method: str = "blackbody",
    filter_file: str | None = None,
    catalog: str | None = None,
) -> ConversionResult:
    """Convenience wrapper: resolve the catalogue, build a converter, convert once."""
    spec = resolve_catalog(catalog)
    converter = build_converter(spec, output_band, conversion_method, filter_file)
    return converter.convert(magnitude_arrays)


# Loader kept public so callers can validate a user filter file before a full run.
__all__ = [
    "ConversionResult",
    "PhotometricConverter",
    "build_converter",
    "convert_magnitudes",
    "load_filter",
    "STATUS_NAMES",
]
