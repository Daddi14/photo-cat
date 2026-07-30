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
- ``sed``       spectral energy distribution models (blackbody now; slots for more).
- ``conversion`` the engine: colour -> Teff -> output/input flux ratio -> magnitude.

Because contamination uses only flux *ratios* within one band, the absolute
zero-point of the output band cancels. The conversion keeps the catalogue band's
zero-point, so a source's converted magnitude is ratio-safe by construction.

Scope: a blackbody colour-to-band conversion is an approximate, catalogue-level
screening estimate. Real stars are not blackbodies, and the reported effective
temperature is a blackbody-equivalent colour temperature, not a physical Teff.
"""

from __future__ import annotations

from .catalogs import CATALOGS, CatalogSpec, resolve_catalog
from .conversion import ConversionResult, PhotometricConverter, convert_magnitudes
from .filters import FilterCurve, load_filter
from .library import available_output_bands, resolve_output_filter
from .sed import SED_MODELS, SUPPORTED_CONVERSION_METHODS

__all__ = [
    "CATALOGS",
    "CatalogSpec",
    "resolve_catalog",
    "ConversionResult",
    "PhotometricConverter",
    "convert_magnitudes",
    "FilterCurve",
    "load_filter",
    "available_output_bands",
    "resolve_output_filter",
    "SED_MODELS",
    "SUPPORTED_CONVERSION_METHODS",
]
