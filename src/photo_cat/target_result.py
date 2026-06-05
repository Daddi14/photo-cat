# SPDX-License-Identifier: GPL-3.0-only
"""Data model for one analysed target source."""

from dataclasses import dataclass


@dataclass
class TargetResult:
    """Contamination summary for one target source."""

    source_id: str
    ra: float
    dec: float
    phot_g_mean_mag: float | None
    flux_fraction_extra: float
    num_contaminants: int
    contaminants: list[dict]
