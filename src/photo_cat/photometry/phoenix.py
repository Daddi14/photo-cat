# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Local PHOENIX-grid interpolation and synthetic photometry.

The module deliberately has no network path.  A prepared grid is described by a
``grid_index.csv`` with, at minimum, these columns::

    teff,logg,mh,filename

Spectrum filenames are relative to the index and contain wavelength and
``F_lambda`` in their first two whitespace-separated columns.  Wavelengths are
nanometres by default; an optional ``wavelength_unit`` column accepts ``nm``,
``angstrom``/``aa``, or ``micron``/``um``.  PHOENIX spectra are energy densities
by default, and are converted to photon-counting density before passband
integration.  Set an optional ``flux_kind`` column to ``photon`` when a prepared
grid has already made that conversion.

Only complete local cells are interpolated.  This matters for BT-Settl grids,
whose coverage is not necessarily a complete Cartesian product: being inside the
global min/max box is not enough to claim that a model exists.
"""

from __future__ import annotations

import csv
import itertools
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Protocol

import numpy as np

from .filters import FilterCurve

_trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")


class PhoenixGridError(ValueError):
    """Base error for malformed or unusable local PHOENIX data."""


class PhoenixGridCoverageError(PhoenixGridError):
    """Raised when a requested atmospheric point has no complete grid cell."""


@dataclass(frozen=True)
class PhoenixSpectrum:
    """One PHOENIX spectral shape sampled as photon flux density."""

    wavelength_nm: np.ndarray
    photon_flux_density: np.ndarray
    # W(lambda) used in the passband-average denominator. Energy F_lambda grids
    # converted to photon rates use lambda; already-photon grids use one.
    band_weight: np.ndarray | None = None


@dataclass(frozen=True)
class PhoenixPhotometryResult:
    """Synthetic target-band result for one normalized PHOENIX spectrum."""

    target_flux: float
    target_mag: float
    sed_model: str
    teff: float
    logg: float
    mh: float
    normalization_factor: float
    quality: str
    extinction_applied: bool

    def metadata(self) -> dict[str, Any]:
        """Return the JSON-safe public representation requested by the pipeline."""
        return {
            "target_flux": self.target_flux,
            "target_mag": self.target_mag,
            "sed_model": self.sed_model,
            "teff": self.teff,
            "logg": self.logg,
            "mh": self.mh,
            "normalization_factor": self.normalization_factor,
            "quality": self.quality,
            "extinction_applied": self.extinction_applied,
        }


@dataclass(frozen=True)
class _GridEntry:
    teff: float
    logg: float
    mh: float
    path: Path
    wavelength_unit: str
    flux_kind: str


def _normalized_header(value: str) -> str:
    return "".join(character for character in value.strip().lower() if character.isalnum())


def _find_column(fieldnames: Iterable[str], *aliases: str) -> str | None:
    by_normalized = {_normalized_header(name): name for name in fieldnames}
    for alias in aliases:
        match = by_normalized.get(_normalized_header(alias))
        if match is not None:
            return match
    return None


def _wavelength_scale(unit: str) -> float:
    normalized = unit.strip().lower().replace("å", "angstrom")
    if normalized in {"", "nm", "nanometer", "nanometre", "nanometers", "nanometres"}:
        return 1.0
    if normalized in {"a", "aa", "angstrom", "angstroms"}:
        return 0.1
    if normalized in {"um", "micron", "microns", "micrometer", "micrometre"}:
        return 1000.0
    raise PhoenixGridError(f"Unsupported PHOENIX wavelength unit: {unit!r}.")


@lru_cache(maxsize=256)
def _load_spectrum(path_text: str, wavelength_unit: str, flux_kind: str) -> PhoenixSpectrum:
    path = Path(path_text)
    try:
        values = np.loadtxt(path, comments="#", usecols=(0, 1), dtype=np.float64)
    except (OSError, ValueError) as error:
        raise PhoenixGridError(f"Could not read PHOENIX spectrum: {path}") from error
    if values.ndim != 2 or values.shape[0] < 2 or values.shape[1] != 2:
        raise PhoenixGridError(f"PHOENIX spectrum needs at least two wavelength/flux rows: {path}")

    wavelength = values[:, 0] * _wavelength_scale(wavelength_unit)
    density = values[:, 1]
    finite = np.isfinite(wavelength) & np.isfinite(density)
    wavelength = wavelength[finite]
    density = density[finite]
    order = np.argsort(wavelength, kind="stable")
    wavelength = wavelength[order]
    density = density[order]
    distinct = np.concatenate(([True], np.diff(wavelength) > 0.0))
    wavelength = wavelength[distinct]
    density = density[distinct]
    if wavelength.size < 2 or wavelength[0] <= 0.0 or np.any(density < 0.0):
        raise PhoenixGridError(f"PHOENIX spectrum has invalid wavelength or flux values: {path}")

    normalized_kind = flux_kind.strip().lower().replace("-", "_")
    if normalized_kind in {"", "energy", "energy_density", "flambda", "f_lambda"}:
        # Photon rate F_photon = F_lambda / (hc/lambda).  The omitted 1/hc is
        # constant at every wavelength and cancels when Gaia G normalizes the SED.
        density = density * wavelength
        band_weight = wavelength.copy()
    elif normalized_kind not in {"photon", "photon_density", "photon_counting"}:
        raise PhoenixGridError(f"Unsupported PHOENIX flux_kind {flux_kind!r} in {path}.")
    else:
        band_weight = np.ones(wavelength.shape, dtype=np.float64)
    if not np.any(density > 0.0):
        raise PhoenixGridError(f"PHOENIX spectrum contains no positive flux: {path}")
    return PhoenixSpectrum(wavelength, density, band_weight)


class PhoenixGrid:
    """A validated, lazily loaded local grid of PHOENIX spectra."""

    def __init__(self, index_path: str | Path) -> None:
        supplied = Path(index_path).expanduser().resolve()
        self.index_path = supplied / "grid_index.csv" if supplied.is_dir() else supplied
        if not self.index_path.is_file():
            raise PhoenixGridError(
                "PHOENIX grid index was not found. Expected grid_index.csv at: "
                f"{self.index_path}"
            )
        self._entries = self._read_index(self.index_path)
        self._teff_axis = np.unique([point[0] for point in self._entries])
        self._logg_axis = np.unique([point[1] for point in self._entries])
        self._mh_axis = np.unique([point[2] for point in self._entries])

    @staticmethod
    def _read_index(index_path: Path) -> dict[tuple[float, float, float], _GridEntry]:
        try:
            with index_path.open("r", encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                fieldnames = reader.fieldnames or []
                teff_column = _find_column(fieldnames, "teff", "teff_k", "effective_temperature")
                logg_column = _find_column(fieldnames, "logg", "log_g")
                mh_column = _find_column(fieldnames, "mh", "metallicity", "[M/H]")
                filename_column = _find_column(fieldnames, "filename", "file", "path", "spectrum")
                unit_column = _find_column(fieldnames, "wavelength_unit", "wave_unit", "unit")
                kind_column = _find_column(fieldnames, "flux_kind", "flux_type")
                required = {
                    "teff": teff_column,
                    "logg": logg_column,
                    "mh": mh_column,
                    "filename": filename_column,
                }
                missing = [name for name, column in required.items() if column is None]
                if missing:
                    raise PhoenixGridError(
                        f"PHOENIX grid index is missing column(s): {', '.join(missing)}: {index_path}"
                    )

                entries: dict[tuple[float, float, float], _GridEntry] = {}
                for row_number, row in enumerate(reader, start=2):
                    try:
                        teff = float(row[teff_column])
                        logg = float(row[logg_column])
                        mh = float(row[mh_column])
                        filename = str(row[filename_column]).strip()
                    except (KeyError, TypeError, ValueError) as error:
                        raise PhoenixGridError(
                            f"Invalid PHOENIX grid parameters on row {row_number}: {index_path}"
                        ) from error
                    if not (np.isfinite(teff) and np.isfinite(logg) and np.isfinite(mh)) or teff <= 0.0:
                        raise PhoenixGridError(
                            f"Invalid PHOENIX grid parameters on row {row_number}: {index_path}"
                        )
                    spectrum_path = (index_path.parent / filename).resolve()
                    if not spectrum_path.is_file():
                        raise PhoenixGridError(
                            f"PHOENIX spectrum listed on row {row_number} does not exist: {spectrum_path}"
                        )
                    key = (teff, logg, mh)
                    if key in entries:
                        raise PhoenixGridError(f"Duplicate PHOENIX grid point {key}: {index_path}")
                    unit = str(row.get(unit_column, "nm") if unit_column else "nm").strip() or "nm"
                    kind = str(row.get(kind_column, "energy") if kind_column else "energy").strip() or "energy"
                    entries[key] = _GridEntry(teff, logg, mh, spectrum_path, unit, kind)
        except OSError as error:
            raise PhoenixGridError(f"Could not read PHOENIX grid index: {index_path}") from error
        if not entries:
            raise PhoenixGridError(f"PHOENIX grid index contains no models: {index_path}")
        return entries

    @property
    def bounds(self) -> dict[str, tuple[float, float]]:
        """Return the global parameter bounds for provenance and diagnostics."""
        return {
            "teff": (float(self._teff_axis[0]), float(self._teff_axis[-1])),
            "logg": (float(self._logg_axis[0]), float(self._logg_axis[-1])),
            "mh": (float(self._mh_axis[0]), float(self._mh_axis[-1])),
        }

    @staticmethod
    def _bracket(axis: np.ndarray, value: float, label: str) -> tuple[float, float, float]:
        if not np.isfinite(value) or value < axis[0] or value > axis[-1]:
            raise PhoenixGridCoverageError(f"{label}={value:g} is outside the PHOENIX grid.")
        position = int(np.searchsorted(axis, value, side="left"))
        if position < axis.size and np.isclose(axis[position], value, rtol=0.0, atol=1e-10):
            exact = float(axis[position])
            return exact, exact, 0.0
        if position == 0 or position == axis.size:
            raise PhoenixGridCoverageError(f"{label}={value:g} is outside the PHOENIX grid.")
        lower = float(axis[position - 1])
        upper = float(axis[position])
        return lower, upper, (float(value) - lower) / (upper - lower)

    def interpolate(self, teff: float, logg: float, mh: float) -> PhoenixSpectrum:
        """Return the tri-linearly interpolated spectrum at one atmospheric point.

        Exact grid coordinates collapse the corresponding interpolation dimension,
        so points on a face, edge, or node need four, two, or one model respectively.
        """
        brackets = (
            self._bracket(self._teff_axis, float(teff), "teff"),
            self._bracket(self._logg_axis, float(logg), "logg"),
            self._bracket(self._mh_axis, float(mh), "mh"),
        )
        choices = [((low,) if low == high else (low, high)) for low, high, _ in brackets]
        corners: list[tuple[float, float, float]] = [
            (teff_corner, logg_corner, mh_corner)
            for teff_corner, logg_corner, mh_corner in itertools.product(
                choices[0], choices[1], choices[2]
            )
        ]
        missing = [corner for corner in corners if corner not in self._entries]
        if missing:
            raise PhoenixGridCoverageError(
                "PHOENIX interpolation cell is incomplete; missing grid point(s): "
                + ", ".join(str(point) for point in missing[:4])
            )

        spectra: list[tuple[float, PhoenixSpectrum]] = []
        for corner in corners:
            weight = 1.0
            for coordinate, (lower, upper, fraction) in zip(corner, brackets):
                if lower != upper:
                    weight *= (1.0 - fraction) if coordinate == lower else fraction
            entry = self._entries[corner]
            spectra.append((weight, _load_spectrum(str(entry.path), entry.wavelength_unit, entry.flux_kind)))

        reference_wave = spectra[0][1].wavelength_nm
        reference_weight = spectra[0][1].band_weight
        combined = np.zeros(reference_wave.shape, dtype=np.float64)
        for weight, spectrum in spectra:
            if np.array_equal(spectrum.wavelength_nm, reference_wave):
                density = spectrum.photon_flux_density
            else:
                if spectrum.wavelength_nm[0] > reference_wave[0] or spectrum.wavelength_nm[-1] < reference_wave[-1]:
                    raise PhoenixGridError("PHOENIX corner spectra do not share a common wavelength range.")
                density = np.interp(reference_wave, spectrum.wavelength_nm, spectrum.photon_flux_density)
            if reference_weight is not None and spectrum.band_weight is not None:
                corner_weight = np.interp(reference_wave, spectrum.wavelength_nm, spectrum.band_weight)
                if not np.allclose(corner_weight, reference_weight):
                    raise PhoenixGridError("PHOENIX grid mixes incompatible energy and photon spectra.")
            combined += weight * density
        if not np.all(np.isfinite(combined)) or not np.any(combined > 0.0):
            raise PhoenixGridError("Interpolated PHOENIX spectrum is not finite and positive.")
        return PhoenixSpectrum(
            reference_wave.copy(),
            combined,
            None if reference_weight is None else reference_weight.copy(),
        )


def extinction_transmission(
    wavelength_nm: np.ndarray,
    azero: float,
    rv: float = 3.1,
) -> np.ndarray:
    """Return a CCM89 extinction transmission normalized to ``A0`` at 541.4 nm.

    The optical polynomial and infrared power law are sufficient for the stellar
    passbands PHOTO-CAT ships.  The IR law is continued redward of its formal
    3.3-micron edge so an optional extinction does not abruptly jump to zero in
    longer Ariel bands.
    """
    wavelength = np.asarray(wavelength_nm, dtype=np.float64)
    if not np.isfinite(azero) or azero < 0.0:
        raise ValueError("azero must be finite and non-negative.")
    if not np.isfinite(rv) or rv <= 0.0:
        raise ValueError("extinction R_V must be finite and positive.")

    def relative_curve(wave: np.ndarray) -> np.ndarray:
        x = np.minimum(1000.0 / wave, 10.0)  # inverse microns; CCM89 is defined to x=10
        a = np.empty(x.shape, dtype=np.float64)
        b = np.empty(x.shape, dtype=np.float64)
        infrared = x < 1.1
        a[infrared] = 0.574 * np.power(x[infrared], 1.61)
        b[infrared] = -0.527 * np.power(x[infrared], 1.61)
        optical = (x >= 1.1) & (x < 3.3)
        y = x[optical] - 1.82
        a[optical] = np.polynomial.polynomial.polyval(
            y,
            (1.0, 0.17699, -0.50447, -0.02427, 0.72085, 0.01979, -0.77530, 0.32999),
        )
        b[optical] = np.polynomial.polynomial.polyval(
            y,
            (0.0, 1.41338, 2.28305, 1.07233, -5.38434, -0.62251, 5.30260, -2.09002),
        )
        ultraviolet = (x >= 3.3) & (x < 8.0)
        xu = x[ultraviolet]
        fa = np.zeros(xu.shape, dtype=np.float64)
        fb = np.zeros(xu.shape, dtype=np.float64)
        high_uv = xu >= 5.9
        yu = xu[high_uv] - 5.9
        fa[high_uv] = -0.04473 * yu**2 - 0.009779 * yu**3
        fb[high_uv] = 0.2130 * yu**2 + 0.1207 * yu**3
        a[ultraviolet] = (
            1.752 - 0.316 * xu - 0.104 / ((xu - 4.67) ** 2 + 0.341) + fa
        )
        b[ultraviolet] = (
            -3.090 + 1.825 * xu + 1.206 / ((xu - 4.62) ** 2 + 0.263) + fb
        )
        far_uv = x >= 8.0
        yf = x[far_uv] - 8.0
        a[far_uv] = -1.073 - 0.628 * yf + 0.137 * yf**2 - 0.070 * yf**3
        b[far_uv] = 13.670 + 4.257 * yf - 0.420 * yf**2 + 0.374 * yf**3
        return a + b / rv

    raw = relative_curve(wavelength)
    reference = float(relative_curve(np.array([541.4], dtype=np.float64))[0])
    a_lambda = float(azero) * raw / reference
    return np.power(10.0, -0.4 * np.maximum(a_lambda, 0.0))


def synthetic_photometry(spectrum: PhoenixSpectrum, filter_curve: FilterCurve) -> float:
    """Return the throughput-weighted mean photon flux in an existing filter."""
    positive = filter_curve.throughput > 0.0
    if not np.any(positive):
        raise ValueError(f"Filter {filter_curve.name!r} has no positive throughput.")
    required_wave = filter_curve.wavelength_nm[positive]
    if required_wave[0] < spectrum.wavelength_nm[0] or required_wave[-1] > spectrum.wavelength_nm[-1]:
        raise ValueError(
            f"PHOENIX spectrum does not cover the positive throughput of filter {filter_curve.name!r}."
        )
    density = np.interp(filter_curve.wavelength_nm, spectrum.wavelength_nm, spectrum.photon_flux_density)
    numerator = float(_trapezoid(density * filter_curve.throughput, filter_curve.wavelength_nm))
    if spectrum.band_weight is None:
        weight = np.ones(filter_curve.wavelength_nm.shape, dtype=np.float64)
    else:
        weight = np.interp(filter_curve.wavelength_nm, spectrum.wavelength_nm, spectrum.band_weight)
    denominator = float(_trapezoid(filter_curve.throughput * weight, filter_curve.wavelength_nm))
    flux = numerator / denominator if denominator > 0.0 else np.nan
    if not np.isfinite(flux) or flux <= 0.0:
        raise ValueError(f"Synthetic flux in filter {filter_curve.name!r} is not positive and finite.")
    return flux


class SpectrumSource(Protocol):
    """Anything that can produce a model spectrum at a set of parameters.

    The conversion only ever asks a grid for one spectrum, so a local directory of
    files and a grid that fetches its nodes on demand are interchangeable here.
    """

    def interpolate(self, teff: float, logg: float, mh: float) -> PhoenixSpectrum:
        """Return the model spectrum at one set of atmospheric parameters."""


def convert_phoenix_photometry(
    grid: SpectrumSource,
    *,
    teff: float,
    logg: float,
    mh: float,
    gaia_g_magnitude: float,
    gaia_g_filter: FilterCurve,
    target_filter: FilterCurve,
    azero: float | None = None,
    apply_extinction: bool = False,
    extinction_rv: float = 3.1,
    quality: str = "high",
) -> PhoenixPhotometryResult:
    """Interpolate, optionally redden, normalize on Gaia G, and integrate a target band."""
    if not np.isfinite(gaia_g_magnitude):
        raise ValueError("Gaia G magnitude must be finite for PHOENIX normalization.")
    spectrum = grid.interpolate(teff, logg, mh)
    extinction_applied = False
    if apply_extinction and azero is not None and np.isfinite(azero):
        extinction_applied = True
        transmission = extinction_transmission(spectrum.wavelength_nm, azero, extinction_rv)
        spectrum = PhoenixSpectrum(
            spectrum.wavelength_nm,
            spectrum.photon_flux_density * transmission,
            spectrum.band_weight,
        )

    model_gaia_flux = synthetic_photometry(spectrum, gaia_g_filter)
    observed_gaia_flux = float(10.0 ** (-0.4 * float(gaia_g_magnitude)))
    normalization = observed_gaia_flux / model_gaia_flux
    model_target_flux = synthetic_photometry(spectrum, target_filter)
    target_flux = normalization * model_target_flux
    if not np.isfinite(target_flux) or target_flux <= 0.0:
        raise ValueError("Normalized PHOENIX target flux is not positive and finite.")
    target_mag = -2.5 * np.log10(target_flux)
    return PhoenixPhotometryResult(
        target_flux=float(target_flux),
        target_mag=float(target_mag),
        sed_model="phoenix",
        teff=float(teff),
        logg=float(logg),
        mh=float(mh),
        normalization_factor=float(normalization),
        quality=quality,
        extinction_applied=extinction_applied,
    )


__all__ = [
    "PhoenixGrid",
    "PhoenixGridCoverageError",
    "PhoenixGridError",
    "PhoenixPhotometryResult",
    "PhoenixSpectrum",
    "convert_phoenix_photometry",
    "extinction_transmission",
    "synthetic_photometry",
]
