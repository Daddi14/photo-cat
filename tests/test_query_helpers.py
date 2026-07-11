# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Focused unit tests for stable contamination-query helpers."""

from __future__ import annotations

import numpy as np
import pytest

from photo_cat.query_contamination_from_index import (
    calculate_flux_fraction_extra,
    contamination_weights,
    source_id_from_internal_id,
    valid_neighbor_indices,
)
from photo_cat.load_config import ContaminationModelConfig


@pytest.mark.unit
def test_source_id_from_internal_id_handles_numeric_and_special_catalogue_ids() -> None:
    """Public results must preserve numeric IDs and original string identifiers."""
    real_ids = np.array([1001, -1], dtype=np.int64)
    special_names = {2: "HD 216608A"}

    assert source_id_from_internal_id(1, real_ids, special_names) == "1001"
    assert source_id_from_internal_id(2, real_ids, special_names) == "HD 216608A"
    assert source_id_from_internal_id(3, real_ids, special_names) == ""


@pytest.mark.unit
def test_valid_neighbor_indices_discards_invalid_one_based_ids() -> None:
    """Corrupt or stale index entries must not read beyond catalogue array boundaries."""
    indices = valid_neighbor_indices(np.array([1, 3, 0, 4, -2]), number_of_sources=3)

    assert indices.tolist() == [0, 2]


@pytest.mark.unit
def test_calculate_flux_fraction_extra_uses_pogson_flux_ratio() -> None:
    """A contaminant one magnitude fainter contributes 10**-0.4 of target flux."""
    result = calculate_flux_fraction_extra(
        target_magnitude=10.0,
        contaminant_magnitudes=np.array([11.0, 15.0]),
        selected_contaminants=np.array([True, False]),
    )

    assert result == pytest.approx((10.0 ** -0.4) * 100.0)


@pytest.mark.unit
def test_flux_fraction_accepts_aperture_weights() -> None:
    """Weighted models should reduce flux contribution without changing the legacy formula."""
    result = calculate_flux_fraction_extra(
        target_magnitude=10.0,
        contaminant_magnitudes=np.array([10.0, 10.0]),
        selected_contaminants=np.array([True, True]),
        weights=np.array([1.0, 0.25]),
    )

    assert result == pytest.approx(125.0)


@pytest.mark.unit
def test_gaussian_contamination_weights_decline_with_radius() -> None:
    """The Gaussian model should be opt-in and radial."""
    weights = contamination_weights(
        np.array([0.0, 10.0, 20.0]),
        ContaminationModelConfig(mode="gaussian_psf", gaussian_fwhm_arcsec=10.0),
    )

    assert weights[0] == pytest.approx(1.0)
    assert weights[0] > weights[1] > weights[2]


@pytest.mark.unit
def test_gaussian_aperture_models_offset_flux_and_normalizes_target() -> None:
    """Integrated Gaussian throughput should include diminishing light beyond the aperture edge."""
    weights = contamination_weights(
        np.array([0.0, 10.0, 30.0]),
        ContaminationModelConfig(mode="gaussian_aperture", gaussian_fwhm_arcsec=10.0),
        aperture_radius_arcsec=10.0,
    )

    assert weights[0] == pytest.approx(1.0)
    assert 0.0 < weights[2] < weights[1] < weights[0]


@pytest.mark.unit
def test_top_hat_has_no_flux_response_outside_aperture() -> None:
    """The compatibility top-hat model must not invent leakage in an expanded influence radius."""
    weights = contamination_weights(
        np.array([9.0, 11.0]),
        ContaminationModelConfig(mode="top_hat"),
        aperture_radius_arcsec=10.0,
    )

    assert weights.tolist() == [1.0, 0.0]
