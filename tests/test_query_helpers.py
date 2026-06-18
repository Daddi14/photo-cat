# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Focused unit tests for stable contamination-query helpers."""

from __future__ import annotations

import numpy as np
import pytest

from photo_cat.query_contamination_from_index import (
    calculate_flux_fraction_extra,
    source_id_from_internal_id,
    valid_neighbor_indices,
)


def test_source_id_from_internal_id_handles_numeric_and_special_catalogue_ids() -> None:
    """Public results must preserve numeric IDs and original string identifiers."""
    real_ids = np.array([1001, -1], dtype=np.int64)
    special_names = {2: "HD 216608A"}

    assert source_id_from_internal_id(1, real_ids, special_names) == "1001"
    assert source_id_from_internal_id(2, real_ids, special_names) == "HD 216608A"
    assert source_id_from_internal_id(3, real_ids, special_names) == ""


def test_valid_neighbor_indices_discards_invalid_one_based_ids() -> None:
    """Corrupt or stale index entries must not read beyond catalogue array boundaries."""
    indices = valid_neighbor_indices(np.array([1, 3, 0, 4, -2]), number_of_sources=3)

    assert indices.tolist() == [0, 2]


def test_calculate_flux_fraction_extra_uses_pogson_flux_ratio() -> None:
    """A contaminant one magnitude fainter contributes 10**-0.4 of target flux."""
    result = calculate_flux_fraction_extra(
        target_magnitude=10.0,
        contaminant_magnitudes=np.array([11.0, 15.0]),
        inside_field_of_view=np.array([True, False]),
    )

    assert result == pytest.approx((10.0 ** -0.4) * 100.0)
