# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Data model for one neighbouring source selected as a contaminant."""

from dataclasses import dataclass


@dataclass
class Contaminant:
    """A catalogue neighbour that contributes flux inside the target aperture."""

    source_id: str
    ra: float
    dec: float
    phot_g_mean_mag: float | None
    sep_arcsec: float
