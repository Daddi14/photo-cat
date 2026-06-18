# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Focused unit tests for stable neighbour-index numerical helpers."""

from __future__ import annotations

import numpy as np
import pytest

from photo_cat.build_neighbors_index import (
    calculate_neighbor_separations_arcsec,
    compute_chord_radius,
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
