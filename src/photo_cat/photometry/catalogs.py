# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Catalogue descriptors: which bands a catalogue provides and how to colour it.

A descriptor is pure declaration. It names the measured flux-anchor band, the two
bands whose difference gives the colour used to estimate temperature, and the
library filter each band maps to. Adding a catalogue (Pan-STARRS, SDSS, 2MASS, ...)
is one entry here; the conversion engine never changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogSpec:
    """Declares a catalogue's bands, colour, and colour->temperature anchor."""

    name: str
    anchor_band: str
    colour_band_1: str
    colour_band_2: str
    # Catalogue band key -> built-in filter band key. Usually identical.
    band_filters: dict[str, str]
    # One physical anchor removes the colour zero-point offset between a blackbody's
    # instrumental colour and the catalogue's calibrated colour: the Sun.
    solar_colour: float
    solar_teff_kelvin: float

    @property
    def colour_bands(self) -> tuple[str, str]:
        """Return the two catalogue bands whose difference is the colour."""
        return (self.colour_band_1, self.colour_band_2)

    @property
    def required_bands(self) -> tuple[str, ...]:
        """Return the catalogue bands the conversion needs present in the index."""
        return tuple(dict.fromkeys((self.anchor_band, self.colour_band_1, self.colour_band_2)))


# Gaia DR3: G is the flux anchor, BP-RP is the colour. Solar BP-RP ~ 0.82 at
# Teff 5772 K anchors the blackbody colour scale (Gaia Collaboration; IAU nominal).
GAIA_DR3 = CatalogSpec(
    name="gaia_dr3",
    anchor_band="gaia_g",
    colour_band_1="gaia_bp",
    colour_band_2="gaia_rp",
    band_filters={"gaia_g": "gaia_g", "gaia_bp": "gaia_bp", "gaia_rp": "gaia_rp"},
    solar_colour=0.82,
    solar_teff_kelvin=5772.0,
)

CATALOGS: dict[str, CatalogSpec] = {GAIA_DR3.name: GAIA_DR3}


def resolve_catalog(name: str | None) -> CatalogSpec:
    """Return the catalogue descriptor for a name, defaulting to Gaia DR3."""
    key = (name or GAIA_DR3.name).strip().lower().replace("-", "_")
    if (key not in CATALOGS):
        available = ", ".join(sorted(CATALOGS))
        raise ValueError(f"Unknown catalogue '{name}'. Available catalogues: {available}.")
    return CATALOGS[key]
