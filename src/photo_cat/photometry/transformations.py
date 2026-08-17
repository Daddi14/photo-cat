# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Published empirical colour transformations from Gaia photometry to other systems.

Where the blackbody method assumes a spectral shape and integrates it through a
transmission curve, these relations are fitted directly to real stars: the Gaia
collaboration regressed ``G - X`` against a Gaia colour on large cross-matched
samples. Inside their calibrated colour range they carry no SED assumption at all,
which makes them the better choice for the photometric systems they cover.

They are also strictly bounded. A relation exists only for the systems Gaia
calibrated, only for the colour interval it was fitted over, and only with the
scatter published alongside it. Nothing here extrapolates: a band without a
relation is refused, and a colour outside the published interval is reported
rather than silently evaluated. In particular there is no Gaia relation to any
mission passband (Ariel, MAUVE, TESS, CHEOPS, ...); those stay with the
blackbody-plus-filter-profile method, which is a different technique, not a
lesser version of this one.

All relations kept here use ``G_BP - G_RP`` as the predictor, because that is the
colour PHOTO-CAT already derives from the catalogue. The published tables also
give relations predicted by external colours (``B-V``, ``V-I``, ``g-i``, ...);
those need photometry PHOTO-CAT does not hold and are therefore not included.

Source: Gaia DR3 online documentation, Sect. 5.5.1 "Photometric relationships with
other photometric systems", Tables 5.9 (coefficients and scatter) and 5.10
(validity ranges), derived from Gaia EDR3 photometry in Riello et al. (2021),
A&A 649, A3. Coefficients are transcribed verbatim from those tables.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .library import normalized_band_key

GAIA_PHOTOMETRY_REFERENCE = (
    "Riello et al. 2021, A&A 649, A3; Gaia DR3 documentation Sect. 5.5.1, Tables 5.9-5.10"
)

# The catalogue these relations are calibrated against. They regress a Gaia colour,
# so they are meaningless for any other catalogue's photometry.
GAIA_TRANSFORMATION_CATALOG = "gaia_dr3"

_COLOUR_NAME = "G_BP-G_RP"


@dataclass(frozen=True)
class ColourTransformation:
    """One published relation ``G - X = sum(c_n * colour^n)`` with its limits.

    The coefficients are stored exactly as published, for ``G - X``, so the output
    magnitude is ``X = G - polynomial(colour)``. Keeping the published orientation
    means the numbers in this file can be diffed against the source tables directly.
    """

    band: str
    system: str
    relation: str
    coefficients: tuple[float, ...]
    colour_min: float
    colour_max: float
    scatter_mag: float
    reference: str = GAIA_PHOTOMETRY_REFERENCE
    colour_name: str = _COLOUR_NAME
    note: str = ""

    def colour_offset(self, colour: np.ndarray) -> np.ndarray:
        """Return the published ``G - X`` polynomial evaluated at each colour."""
        return np.polynomial.polynomial.polyval(colour, self.coefficients)

    def apply(self, anchor_magnitude: np.ndarray, colour: np.ndarray) -> np.ndarray:
        """Return the output-band magnitude ``X = G - (G - X)``."""
        return anchor_magnitude - self.colour_offset(colour)

    def within_range(self, colour: np.ndarray) -> np.ndarray:
        """Return the mask of colours inside the published validity interval.

        The interval is inclusive of its endpoints: the published bounds are the
        edge of the calibrated sample, not an open interval, and excluding a source
        sitting exactly on a rounded bound would be an artefact of the rounding.
        """
        return (colour >= self.colour_min) & (colour <= self.colour_max)

    def metadata(self) -> dict[str, Any]:
        """Return the JSON-safe description recorded in the run output."""
        return {
            "band": self.band,
            "system": self.system,
            "relation": self.relation,
            "colour_name": self.colour_name,
            "coefficients": list(self.coefficients),
            "colour_min": self.colour_min,
            "colour_max": self.colour_max,
            "scatter_mag": self.scatter_mag,
            "reference": self.reference,
            "note": self.note,
        }


# Every entry below is transcribed from the published tables: coefficients and
# scatter from Table 5.9, colour interval from Table 5.10, and the "only valid for
# M giants above ..." footnotes as the note. PHOTO-CAT cannot know a source's
# luminosity class, so a footnote is reported rather than enforced.
GAIA_EMPIRICAL_TRANSFORMATIONS: dict[str, ColourTransformation] = {
    # --- Johnson-Cousins -----------------------------------------------------
    "johnson_b": ColourTransformation(
        band="johnson_b",
        system="Johnson-Cousins",
        relation="G-B",
        coefficients=(0.01448, -0.6874, -0.3604, 0.06718, -0.006061),
        colour_min=-0.5,
        colour_max=4.0,
        scatter_mag=0.0633,
        note="Only valid for M giants when G_BP-G_RP > 1.75.",
    ),
    "johnson_v": ColourTransformation(
        band="johnson_v",
        system="Johnson-Cousins",
        relation="G-V",
        coefficients=(-0.02704, 0.01424, -0.2156, 0.01426),
        colour_min=-0.5,
        colour_max=5.0,
        scatter_mag=0.03017,
    ),
    "johnson_r": ColourTransformation(
        band="johnson_r",
        system="Johnson-Cousins",
        relation="G-R",
        coefficients=(-0.02275, 0.3961, -0.1243, -0.01396, 0.003775),
        colour_min=0.0,
        colour_max=4.0,
        scatter_mag=0.03167,
        note="Only valid for M giants when G_BP-G_RP > 2.0.",
    ),
    "cousins_i": ColourTransformation(
        band="cousins_i",
        system="Johnson-Cousins",
        relation="G-I_C",
        coefficients=(0.01753, 0.76, -0.0991),
        colour_min=-0.5,
        colour_max=4.5,
        scatter_mag=0.03765,
    ),
    # --- 2MASS ---------------------------------------------------------------
    "2mass_j": ColourTransformation(
        band="2mass_j",
        system="2MASS",
        relation="G-J",
        coefficients=(0.01798, 1.389, -0.09338),
        colour_min=-0.5,
        colour_max=2.5,
        scatter_mag=0.04762,
    ),
    "2mass_h": ColourTransformation(
        band="2mass_h",
        system="2MASS",
        relation="G-H",
        coefficients=(-0.1048, 2.011, -0.1758),
        colour_min=-0.5,
        colour_max=2.5,
        scatter_mag=0.07805,
    ),
    "2mass_ks": ColourTransformation(
        band="2mass_ks",
        system="2MASS",
        relation="G-K_S",
        coefficients=(-0.0981, 2.089, -0.1579),
        colour_min=-0.5,
        colour_max=2.5,
        scatter_mag=0.08553,
    ),
    # --- SDSS12 --------------------------------------------------------------
    "sdss_g": ColourTransformation(
        band="sdss_g",
        system="SDSS12",
        relation="G-g",
        coefficients=(0.2199, -0.6365, -0.1548, 0.0064),
        colour_min=0.3,
        colour_max=3.0,
        scatter_mag=0.0745,
        note="Only valid for M giants when G_BP-G_RP > 2.0.",
    ),
    "sdss_r": ColourTransformation(
        band="sdss_r",
        system="SDSS12",
        relation="G-r",
        coefficients=(-0.09837, 0.08592, 0.1907, -0.1701, 0.02263),
        colour_min=0.0,
        colour_max=3.0,
        scatter_mag=0.03776,
        note="Only valid for M giants when G_BP-G_RP > 2.0.",
    ),
    "sdss_i": ColourTransformation(
        band="sdss_i",
        system="SDSS12",
        relation="G-i",
        coefficients=(-0.293, 0.6404, -0.09609, -0.002104),
        colour_min=0.5,
        colour_max=2.0,
        scatter_mag=0.04092,
    ),
    "sdss_z": ColourTransformation(
        band="sdss_z",
        system="SDSS12",
        relation="G-z",
        coefficients=(-0.4619, 0.8992, -0.08271, 0.005029),
        colour_min=-0.5,
        colour_max=4.5,
        scatter_mag=0.041161,
    ),
    # --- Hipparcos and Tycho-2 ----------------------------------------------
    "hipparcos_hp": ColourTransformation(
        band="hipparcos_hp",
        system="Hipparcos",
        relation="G-Hp",
        coefficients=(-0.01008, -0.2309, -0.1300, 0.01894),
        colour_min=-0.5,
        colour_max=4.0,
        scatter_mag=0.06066,
    ),
    "tycho_bt": ColourTransformation(
        band="tycho_bt",
        system="Tycho-2",
        relation="G-B_T",
        coefficients=(-0.004288, -0.8547, 0.1244, -0.9085, 0.4843, -0.06814),
        colour_min=-0.3,
        colour_max=3.0,
        scatter_mag=0.07063,
    ),
    "tycho_vt": ColourTransformation(
        band="tycho_vt",
        system="Tycho-2",
        relation="G-V_T",
        coefficients=(-0.01077, -0.0682, -0.2387, 0.02342),
        colour_min=-0.35,
        colour_max=4.0,
        scatter_mag=0.05350,
    ),
}

# Short spellings for the bands whose bare letter has one classical meaning. The
# SDSS bands keep their system prefix: a bare "g" would read as Gaia G, and bare
# "r"/"i" are already the Johnson-Cousins bands here.
_BAND_ALIASES: dict[str, str] = {
    "b": "johnson_b",
    "v": "johnson_v",
    "r": "johnson_r",
    "i": "cousins_i",
    "ic": "cousins_i",
    "johnson_i": "cousins_i",
    "j": "2mass_j",
    "h": "2mass_h",
    "ks": "2mass_ks",
    "z": "sdss_z",
    "hp": "hipparcos_hp",
    "bt": "tycho_bt",
    "vt": "tycho_vt",
}


def supported_empirical_bands() -> list[str]:
    """Return the canonical band keys that have a published Gaia relation."""
    return sorted(GAIA_EMPIRICAL_TRANSFORMATIONS)


def find_transformation(band: str, catalog: str = GAIA_TRANSFORMATION_CATALOG) -> ColourTransformation | None:
    """Return the published relation for a band, or None when there is none.

    The relations regress a Gaia colour, so they are offered only for the
    catalogue they were calibrated on; any other catalogue returns None and the
    caller falls back to an SED-based method.
    """
    if (normalized_band_key(catalog) != GAIA_TRANSFORMATION_CATALOG):
        return None
    key = normalized_band_key(band)
    return GAIA_EMPIRICAL_TRANSFORMATIONS.get(_BAND_ALIASES.get(key, key))


def require_transformation(band: str, catalog: str = GAIA_TRANSFORMATION_CATALOG) -> ColourTransformation:
    """Return the relation for a band, or explain that none is calibrated for it."""
    transformation = find_transformation(band, catalog)
    if (transformation is None):
        supported = ", ".join(supported_empirical_bands())
        raise ValueError(
            f"No calibrated Gaia empirical transformation is available for output band "
            f"'{band}'. Published relations exist only for: {supported}. Mission "
            "passbands (Ariel, MAUVE, TESS, CHEOPS, SVO filters, ...) have no Gaia "
            "relation: use conversion_method 'blackbody', or 'auto' to pick "
            "automatically."
        )
    return transformation
