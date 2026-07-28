# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Data model for one catalogue neighbour selected by query cuts."""

from dataclasses import dataclass


@dataclass
class Contaminant:
    """A neighbour inside the configured angular radius and delta-magnitude cut."""

    source_id: str
    ra: float
    dec: float
    magnitude: float | None
    magnitude_band: str
    magnitude_source: str
    sep_arcsec: float
