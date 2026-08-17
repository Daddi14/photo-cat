# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Convert catalogue magnitudes into a chosen output band.

Two families of method live here, sharing one interface so the rest of PHOTO-CAT
never learns which one ran:

- SED-based (``blackbody``, and ``phoenix`` once its grid exists). Per source:
  colour -> effective temperature -> output/anchor flux ratio -> output-band
  magnitude. The heavy synthetic photometry (integrating the SED through each
  filter) is done once on a temperature grid at construction; per-source work is
  two vectorised ``np.interp`` calls, so converting a whole catalogue is O(N).
  This is the only family that works for an arbitrary transmission curve, which
  is what mission passbands and SVO filters need.
- Empirical (``gaia_empirical``). A published polynomial in the catalogue colour,
  fitted to real stars, evaluated directly. No SED assumption, but it exists only
  for the photometric systems and colour intervals Gaia calibrated.

``auto`` combines them per source: the empirical relation where it is calibrated
and applicable, the SED method everywhere else.

Only flux ratios within one band are ever used downstream, so the output band's
absolute zero-point cancels. The SED conversion keeps the anchor band's zero-point
(``m_out = m_anchor`` when the flux ratio is 1), which makes every converted
magnitude ratio-safe; the empirical relations are published as ``G - X``, so they
land on the output system's own zero-point, which is equally ratio-safe because
every source in a run is converted the same way. The one zero-point that does
affect SED results is the colour scale, anchored to the Sun so a blackbody's
instrumental colour matches the catalogue's calibrated colour at one physical point.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from .catalogs import CatalogSpec, resolve_catalog
from .filters import FilterCurve, load_filter
from .library import library_filter_path, load_library_filter, normalized_band_key, resolve_output_filter
from .sed import SED_MODELS
from .transformations import ColourTransformation, find_transformation, require_transformation

# np.trapezoid is the name from NumPy 2.0; NumPy 1.24-1.x only ships np.trapz.
# getattr for both keeps mypy off the version-specific stub attribute.
_trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")

METHOD_GAIA_EMPIRICAL = "gaia_empirical"
METHOD_AUTO = "auto"
# Selectable conversion methods: the SED models, the published empirical relations,
# and the per-source combination of the two.
SUPPORTED_CONVERSION_METHODS: tuple[str, ...] = (*SED_MODELS, METHOD_GAIA_EMPIRICAL, METHOD_AUTO)

STATUS_MISSING_INPUT = 0
STATUS_VALID = 1
STATUS_CLAMPED = 2
STATUS_OUT_OF_CALIBRATION = 3
STATUS_FALLBACK = 4
STATUS_NAMES = {
    STATUS_MISSING_INPUT: "missing_input",
    STATUS_VALID: "valid",
    STATUS_CLAMPED: "colour_out_of_grid",
    STATUS_OUT_OF_CALIBRATION: "colour_outside_valid_range",
    STATUS_FALLBACK: "converted_by_fallback_method",
}

# Which method actually produced each source's magnitude. ``auto`` mixes the two
# within one run, so the summary needs this alongside the per-source status.
APPLIED_NONE = 0
APPLIED_SED = 1
APPLIED_EMPIRICAL = 2

# Blackbody-equivalent colour temperature is only meaningful over a stellar range;
# the grid is dense enough that linear interpolation is exact to well under a kelvin.
_TEFF_MIN_K = 2000.0
_TEFF_MAX_K = 50000.0
_TEFF_GRID_POINTS = 400


@dataclass(frozen=True)
class ConversionResult:
    """Output-band magnitudes and per-source temperature, status, and method."""

    out_magnitudes: np.ndarray
    effective_temperature: np.ndarray
    status_codes: np.ndarray
    metadata: dict[str, Any]
    # Which method produced each magnitude (APPLIED_* codes). Constant for a
    # single-method run; genuinely per-source under ``auto``.
    applied_method: np.ndarray = field(default_factory=lambda: np.empty(0, dtype=np.uint8))
    summary: dict[str, Any] = field(default_factory=dict)


def _conversion_summary(
    status_codes: np.ndarray,
    applied_method: np.ndarray,
    method_names: dict[int, str],
) -> dict[str, Any]:
    """Count sources by outcome and by the method that actually converted them.

    Reported in the run output so a result can be judged without rerunning it: how
    many sources a published relation covered, how many needed the SED fallback,
    and how many could not be converted at all.
    """
    status_counts = {
        name: int(np.count_nonzero(status_codes == code)) for code, name in STATUS_NAMES.items()
    }
    method_counts = {
        name: int(np.count_nonzero(applied_method == code)) for code, name in method_names.items()
    }
    return {
        "sources": int(status_codes.shape[0]),
        "converted": int(np.count_nonzero(applied_method != APPLIED_NONE)),
        "status_counts": {name: count for name, count in status_counts.items() if count},
        "method_counts": {name: count for name, count in method_counts.items() if count},
    }


def _catalogue_inputs(
    catalog: CatalogSpec, magnitude_arrays: dict[str, np.ndarray]
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return the anchor magnitude, the colour, and the finite-input mask.

    Shared by every method so a missing band or a ragged array fails the same way
    whichever conversion was selected.
    """
    missing = [band for band in catalog.required_bands if band not in magnitude_arrays]
    if (missing):
        raise ValueError(
            "Photometric conversion requires magnitude bands absent from the index: "
            f"{', '.join(missing)}. Rebuild the index with these magnitude_columns."
        )

    anchor = np.asarray(magnitude_arrays[catalog.anchor_band], dtype=np.float64)
    colour_1 = np.asarray(magnitude_arrays[catalog.colour_band_1], dtype=np.float64)
    colour_2 = np.asarray(magnitude_arrays[catalog.colour_band_2], dtype=np.float64)
    if (anchor.ndim != 1 or colour_1.shape != anchor.shape or colour_2.shape != anchor.shape):
        raise ValueError("Photometric conversion magnitude arrays must be aligned 1-D arrays.")

    finite = np.isfinite(anchor) & np.isfinite(colour_1) & np.isfinite(colour_2)
    return anchor, colour_1 - colour_2, finite


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
        anchor, colour, finite = _catalogue_inputs(self.catalog, magnitude_arrays)

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
        applied = np.where(finite, APPLIED_SED, APPLIED_NONE).astype(np.uint8)
        return ConversionResult(
            out_magnitudes=np.asarray(out_magnitudes, dtype=np.float64),
            effective_temperature=np.asarray(temperature, dtype=np.float64),
            status_codes=status,
            metadata=self.metadata,
            applied_method=applied,
            summary=_conversion_summary(status, applied, {APPLIED_SED: self.method}),
        )


class EmpiricalConverter:
    """Apply one published colour relation, strictly inside its calibrated range.

    There is no spectral model and no filter curve: the relation was fitted to
    observed stars, so the output magnitude is the polynomial evaluated at the
    catalogue colour. A source whose colour falls outside the published interval is
    reported as out of calibration rather than extrapolated, and no effective
    temperature is reported because none is derived.
    """

    def __init__(self, catalog: CatalogSpec, output_band: str, transformation: ColourTransformation) -> None:
        self.catalog = catalog
        self.method = METHOD_GAIA_EMPIRICAL
        self.transformation = transformation
        self.output_band = normalized_band_key(output_band)
        # A colour relation always changes the band; there is no identity shortcut.
        self.is_identity = False
        self.output_filter = None
        self.metadata: dict[str, Any] = {
            "catalog": catalog.name,
            "output_band": self.output_band,
            "conversion_method": self.method,
            "anchor_band": catalog.anchor_band,
            "colour_bands": list(catalog.colour_bands),
            "filter_used": None,
            "transformation": transformation.metadata(),
        }

    def convert(self, magnitude_arrays: dict[str, np.ndarray]) -> ConversionResult:
        """Convert with the published relation, flagging uncalibrated colours."""
        anchor, colour, finite = _catalogue_inputs(self.catalog, magnitude_arrays)
        usable = finite & self.transformation.within_range(colour)

        out_magnitudes = np.where(usable, self.transformation.apply(anchor, colour), np.nan)
        status = np.full(anchor.shape, STATUS_MISSING_INPUT, dtype=np.uint8)
        status[finite & ~usable] = STATUS_OUT_OF_CALIBRATION
        status[usable] = STATUS_VALID
        applied = np.where(usable, APPLIED_EMPIRICAL, APPLIED_NONE).astype(np.uint8)

        return ConversionResult(
            out_magnitudes=np.asarray(out_magnitudes, dtype=np.float64),
            # The relation carries no temperature; reporting one would invent it.
            effective_temperature=np.full(anchor.shape, np.nan, dtype=np.float64),
            status_codes=status,
            metadata=self.metadata,
            applied_method=applied,
            summary=_conversion_summary(status, applied, {APPLIED_EMPIRICAL: self.method}),
        )


class AutoConverter:
    """Prefer the published relation per source, fall back to the SED method.

    The empirical relation is used wherever it is calibrated and the source has the
    colour it needs; every other source goes through the SED converter. The fallback
    needs a transmission curve for the output band, so when none is installed the
    uncalibrated sources stay unconverted and say so, rather than being extrapolated.
    """

    def __init__(self, empirical: EmpiricalConverter, fallback: PhotometricConverter | None) -> None:
        self.catalog = empirical.catalog
        self.method = METHOD_AUTO
        self.empirical = empirical
        self.fallback = fallback
        self.is_identity = False
        self.output_filter = None if fallback is None else fallback.output_filter
        self.metadata: dict[str, Any] = {
            **empirical.metadata,
            "conversion_method": METHOD_AUTO,
            "primary_method": empirical.method,
            "fallback_method": None if fallback is None else fallback.method,
            "filter_used": None if fallback is None else fallback.metadata["filter_used"],
        }

    def convert(self, magnitude_arrays: dict[str, np.ndarray]) -> ConversionResult:
        """Convert each source with whichever method is applicable to it."""
        empirical = self.empirical.convert(magnitude_arrays)
        method_names = {APPLIED_EMPIRICAL: self.empirical.method}
        if (self.fallback is None):
            summary = _conversion_summary(empirical.status_codes, empirical.applied_method, method_names)
            summary["fallback_available"] = False
            return ConversionResult(
                out_magnitudes=empirical.out_magnitudes,
                effective_temperature=empirical.effective_temperature,
                status_codes=empirical.status_codes,
                metadata=self.metadata,
                applied_method=empirical.applied_method,
                summary=summary,
            )

        fallback = self.fallback.convert(magnitude_arrays)
        use_empirical = empirical.status_codes == STATUS_VALID
        converted_by_fallback = ~use_empirical & np.isfinite(fallback.out_magnitudes)

        out_magnitudes = np.where(use_empirical, empirical.out_magnitudes, fallback.out_magnitudes)
        temperature = np.where(use_empirical, np.nan, fallback.effective_temperature)
        status = np.where(converted_by_fallback, STATUS_FALLBACK, empirical.status_codes).astype(np.uint8)
        applied = np.where(converted_by_fallback, APPLIED_SED, empirical.applied_method).astype(np.uint8)

        method_names[APPLIED_SED] = self.fallback.method
        summary = _conversion_summary(status, applied, method_names)
        summary["fallback_available"] = True
        return ConversionResult(
            out_magnitudes=np.asarray(out_magnitudes, dtype=np.float64),
            effective_temperature=np.asarray(temperature, dtype=np.float64),
            status_codes=status,
            metadata=self.metadata,
            applied_method=applied,
            summary=summary,
        )


BandConverter = PhotometricConverter | EmpiricalConverter | AutoConverter


def _output_band_has_filter(output_band: str, filter_file: str | None) -> bool:
    """Return whether an SED conversion into this band is even possible.

    Mirrors what ``resolve_output_filter`` will accept, so the fallback is offered
    only when it can actually be built. Checking up front keeps a band with no
    installed curve reportable as such, instead of swallowing that error together
    with the genuine parse errors of a filter file the user did supply.
    """
    if (normalized_band_key(output_band) == "custom"):
        return filter_file is not None
    return library_filter_path(output_band) is not None


def _build_sed_converter(
    catalog: CatalogSpec,
    output_band: str,
    conversion_method: str,
    filter_file: str | None,
) -> PhotometricConverter:
    """Assemble an SED-based converter, loading the anchor, colour, and output filters."""

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


def build_converter(
    catalog: CatalogSpec,
    output_band: str,
    conversion_method: str,
    filter_file: str | None,
) -> BandConverter:
    """Assemble the converter for one method, output band, and catalogue."""
    if (conversion_method not in SUPPORTED_CONVERSION_METHODS):
        supported = ", ".join(SUPPORTED_CONVERSION_METHODS)
        raise ValueError(f"Unknown conversion_method '{conversion_method}'. Supported: {supported}.")

    if (conversion_method == METHOD_GAIA_EMPIRICAL):
        return EmpiricalConverter(catalog, output_band, require_transformation(output_band, catalog.name))

    if (conversion_method == METHOD_AUTO):
        transformation = find_transformation(output_band, catalog.name)
        if (transformation is None):
            # No published relation for this band: this is the ordinary case for
            # mission passbands, and the SED method is the right tool for them.
            return _build_sed_converter(catalog, output_band, "blackbody", filter_file)
        fallback = None
        if (_output_band_has_filter(output_band, filter_file)):
            fallback = _build_sed_converter(catalog, output_band, "blackbody", filter_file)
        return AutoConverter(EmpiricalConverter(catalog, output_band, transformation), fallback)

    return _build_sed_converter(catalog, output_band, conversion_method, filter_file)


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
    "AutoConverter",
    "BandConverter",
    "ConversionResult",
    "EmpiricalConverter",
    "PhotometricConverter",
    "build_converter",
    "convert_magnitudes",
    "load_filter",
    "METHOD_AUTO",
    "METHOD_GAIA_EMPIRICAL",
    "STATUS_NAMES",
    "SUPPORTED_CONVERSION_METHODS",
]
