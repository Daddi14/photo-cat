# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Focused unit tests for stable neighbour-index numerical helpers."""

from __future__ import annotations

import numpy as np
import pytest
from pathlib import Path

from photo_cat.build_neighbors_index import (
    calculate_neighbor_separations_arcsec,
    compute_chord_radius,
    load_star_dataframe,
    neighbor_indices_without_self,
)


@pytest.mark.unit
def test_neighbor_indices_without_self_preserves_neighbour_order() -> None:
    """KDTree self-matches must be removed without reordering actual neighbour positions."""
    indices = neighbor_indices_without_self([3, 7, 3, 9], target_index=3)

    assert indices.dtype == np.int64
    assert indices.tolist() == [7, 9]


@pytest.mark.unit
def test_calculate_neighbor_separations_arcsec_uses_unit_vectors() -> None:
    """A one-degree great-circle separation must remain approximately 3600 arcseconds."""
    coords = np.array([
        [1.0, 0.0, 0.0],
        [np.cos(np.deg2rad(1.0)), np.sin(np.deg2rad(1.0)), 0.0],
    ])

    separations = calculate_neighbor_separations_arcsec(coords, 0, np.array([1], dtype=np.int64))

    assert separations[0] == pytest.approx(3600.0, rel=1e-8)


@pytest.mark.unit
def test_compute_chord_radius_is_positive_for_positive_angular_radius() -> None:
    """The spatial KDTree radius must be positive for a valid angular search radius."""
    assert compute_chord_radius(120.0) > 0.0


@pytest.mark.unit
def test_catalog_rejects_source_ids_that_collide_after_numeric_normalization(tmp_path: Path) -> None:
    """Textually distinct IDs such as 1 and 001 must not resolve ambiguously to one numeric target."""
    catalog_path = tmp_path / "ambiguous.csv"
    catalog_path.write_text(
        "source_id,ra,dec,phot_g_mean_mag\n"
        "1,10.0,20.0,11.0\n"
        "001,11.0,21.0,12.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unique after numeric normalization"):
        load_star_dataframe(str(catalog_path), use_dask=False)


@pytest.mark.unit
def test_catalog_loads_optional_magnitude_bands(tmp_path: Path) -> None:
    """Additional magnitude columns should be preserved for multi-band queries."""
    catalog_path = tmp_path / "multiband.csv"
    catalog_path.write_text(
        "source_id,ra,dec,phot_g_mean_mag,phot_bp_mean_mag\n"
        "1,10.0,20.0,11.0,11.5\n",
        encoding="utf-8",
    )

    dataframe = load_star_dataframe(
        str(catalog_path),
        use_dask=False,
        magnitude_columns={"gaia_g": "phot_g_mean_mag", "gaia_bp": "phot_bp_mean_mag"},
    )

    assert dataframe["magnitude_gaia_bp"].tolist() == [11.5]
