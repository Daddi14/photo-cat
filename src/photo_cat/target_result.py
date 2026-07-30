# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Data model for one analysed target source."""

from dataclasses import dataclass


@dataclass
class TargetResult:
    """Contamination summary for one target source."""

    source_id: str
    ra: float
    dec: float
    magnitude: float | None
    magnitude_band: str
    magnitude_source: str
    flux_fraction_selected: float
    flux_fraction_all_neighbors: float
    flux_fraction_extra: float
    num_neighbors_in_radius: int
    num_contaminants_selected: int
    num_contaminants: int
    contaminants: list[dict]
