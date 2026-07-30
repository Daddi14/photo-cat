# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Spectral energy distribution models used to convert flux between bands.

An SED model maps an effective temperature to a relative spectral shape, sampled
at given wavelengths. Only the shape matters: every use divides one band integral
by another, so any constant scale factor on the SED cancels.

The models are photon-count spectral densities, because the detectors these bands
describe (Gaia, TESS, CHEOPS, ...) count photons rather than integrate energy.

Adding a model is a single registry entry. ``blackbody`` is implemented now;
``phoenix`` and ``empirical`` are selectable but require external data (a model
spectrum grid, or a published colour-band relation) and raise a clear error until
that data is supplied, so wiring them in later needs no change elsewhere.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

# Planck constant * speed of light / Boltzmann constant, in nanometre-kelvin.
# hc/k = 0.014387768775 m*K = 1.4387768775e7 nm*K.
_HC_OVER_K_NM_K = 1.4387768775e7


def blackbody_photon_density(wavelength_nm: np.ndarray, teff_kelvin: float) -> np.ndarray:
    """Return the relative photon spectral density of a blackbody at ``teff_kelvin``.

    Energy spectral radiance is B_lambda ~ 1 / lambda^5 / (exp(hc/lambda k T) - 1).
    A photon carries energy hc/lambda, so the photon rate density is B_lambda times
    lambda/hc, i.e. ~ 1 / lambda^4 / (exp(hc/lambda k T) - 1). Only the shape is
    used, so the constant hc factor is dropped. ``expm1`` keeps the Wien tail stable.
    """
    wavelength = np.asarray(wavelength_nm, dtype=np.float64)
    if (teff_kelvin <= 0.0):
        raise ValueError("Blackbody effective temperature must be positive.")
    exponent = _HC_OVER_K_NM_K / (wavelength * float(teff_kelvin))
    # exp(x) - 1 via expm1 avoids catastrophic cancellation for small x (red/cool tail)
    # and overflows cleanly to +inf for large x (blue/hot tail), giving density -> 0.
    with np.errstate(over="ignore"):
        denominator = np.expm1(exponent)
    density = 1.0 / (wavelength**4 * denominator)
    return np.where(np.isfinite(density), density, 0.0)


def _unavailable_model(name: str, requirement: str) -> Callable[[np.ndarray, float], np.ndarray]:
    """Return a selectable SED model that explains what external data it needs."""

    def model(wavelength_nm: np.ndarray, teff_kelvin: float) -> np.ndarray:
        raise ValueError(
            f"The '{name}' conversion method is selectable but not yet available: it "
            f"requires {requirement}. Use conversion_method: blackbody, or supply the "
            "required data."
        )

    return model


# Registry of SED models keyed by conversion-method name. blackbody is ready; the
# others are honest placeholders so the method can be selected and validated now,
# and filled in later by replacing the entry with no change to the engine.
SED_MODELS: dict[str, Callable[[np.ndarray, float], np.ndarray]] = {
    "blackbody": blackbody_photon_density,
    "phoenix": _unavailable_model("phoenix", "a grid of PHOENIX model spectra"),
    "empirical": _unavailable_model("empirical", "a published colour-to-band relation file"),
}

SUPPORTED_CONVERSION_METHODS = tuple(SED_MODELS)
