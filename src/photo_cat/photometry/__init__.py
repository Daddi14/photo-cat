# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Mission-agnostic photometric band conversion.

PHOTO-CAT measures contamination from catalogue magnitudes, which are tied to the
catalogue's own passband (Gaia G). Real contamination depends on the observed
wavelength: two stars with the same G but different colours contribute very
differently in a bluer or redder mission band.

This package converts each source's flux from the catalogue band into a chosen
mission band before contamination is computed. The conversion is deliberately
modular and separate from the contamination algorithm, which never changes:

- ``filters``   load a transmission curve (built-in or user file) in one format.
- ``library``   discover built-in mission filters under ``photo_cat/filters``.
- ``catalogs``  declare a catalogue's bands, colour, and flux anchor band.
- ``sed``       temperature-only spectral energy distribution models (blackbody).
- ``phoenix``   local atmosphere-grid interpolation and synthetic photometry.
- ``transformations`` published empirical colour relations, with their calibrated
  ranges, for the photometric systems Gaia provides them for.
- ``conversion`` the engine and method dispatch: SED integration, empirical
  relation, or ``auto`` picking between them per source.

Because contamination uses only flux *ratios* within one band, the absolute
zero-point of the output band cancels. The conversion keeps the catalogue band's
zero-point, so a source's converted magnitude is ratio-safe by construction.

Scope: blackbody conversion remains an approximate catalogue-level estimate;
PHOENIX uses precomputed model atmospheres but does not fit them to observations.
"""

from __future__ import annotations

from .catalogs import CATALOGS, CatalogSpec, resolve_catalog
from .conversion import (
    SUPPORTED_CONVERSION_METHODS,
    AutoConverter,
    ConversionResult,
    EmpiricalConverter,
    PhoenixConverter,
    PhotometricConverter,
    convert_magnitudes,
)
from .filters import FilterCurve, load_filter
from .library import available_output_bands, resolve_output_filter
from .sed import SED_MODELS
from .phoenix import (
    PhoenixGrid,
    PhoenixGridCoverageError,
    PhoenixPhotometryResult,
    PhoenixSpectrum,
    convert_phoenix_photometry,
    synthetic_photometry,
)
from .transformations import (
    GAIA_EMPIRICAL_TRANSFORMATIONS,
    ColourTransformation,
    find_transformation,
    supported_empirical_bands,
)

__all__ = [
    "CATALOGS",
    "CatalogSpec",
    "resolve_catalog",
    "AutoConverter",
    "ConversionResult",
    "EmpiricalConverter",
    "PhotometricConverter",
    "PhoenixConverter",
    "convert_magnitudes",
    "FilterCurve",
    "load_filter",
    "available_output_bands",
    "resolve_output_filter",
    "SED_MODELS",
    "PhoenixGrid",
    "PhoenixGridCoverageError",
    "PhoenixPhotometryResult",
    "PhoenixSpectrum",
    "convert_phoenix_photometry",
    "synthetic_photometry",
    "SUPPORTED_CONVERSION_METHODS",
    "GAIA_EMPIRICAL_TRANSFORMATIONS",
    "ColourTransformation",
    "find_transformation",
    "supported_empirical_bands",
]
