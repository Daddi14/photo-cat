# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Focused unit tests for stable contamination-query helpers."""

from __future__ import annotations

import numpy as np
import pytest

from photo_cat.query_contamination_from_index import (
    make_influence_neighbor_provider,
    CONTAMINATION_WEIGHTERS,
    calculate_flux_fraction_extra,
    contamination_weights,
    psf_aperture_metrics,
    source_id_from_internal_id,
    valid_neighbor_indices,
)
from photo_cat.load_config import CONTAMINATION_MODES, GAUSSIAN_FWHM_TO_SIGMA, ContaminationModelConfig


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
def test_top_hat_has_no_flux_response_outside_aperture() -> None:
    """The compatibility top-hat model must not invent leakage in an expanded influence radius."""
    weights = contamination_weights(
        np.array([9.0, 11.0]),
        ContaminationModelConfig(mode="top_hat"),
        aperture_radius_arcsec=10.0,
    )

    assert weights.tolist() == [1.0, 0.0]


@pytest.mark.unit
def test_unsupported_contamination_model_is_rejected() -> None:
    """An unknown model name must fail loudly rather than silently return no weights."""
    with pytest.raises(ValueError, match="Unsupported contamination model"):
        contamination_weights(
            np.array([1.0]),
            ContaminationModelConfig(mode="not_a_real_model"),
        )


@pytest.mark.unit
def test_weighter_registry_covers_exactly_the_supported_modes() -> None:
    """The registry must stay in sync with the modes accepted by the configuration parser."""
    assert set(CONTAMINATION_WEIGHTERS) == set(CONTAMINATION_MODES)


@pytest.mark.unit
def test_psf_aperture_metrics_reports_ratio_purity_and_fraction() -> None:
    """An equal-magnitude contaminant on the target gives C=1, P=0.5, and 1-P=0.5."""
    model = ContaminationModelConfig(mode="gaussian_psf", gaussian_fwhm_arcsec=5.0)
    metrics = psf_aperture_metrics(
        10.0,
        np.array([10.0]),
        np.array([True]),
        np.array([0.0]),
        model,
        aperture_radius_arcsec=10.0,
    )

    assert metrics is not None
    assert metrics["contamination_ratio"] == pytest.approx(1.0)
    assert metrics["target_purity"] == pytest.approx(0.5)
    assert metrics["contaminating_fraction"] == pytest.approx(0.5)
    # The PSF width used for the metrics is reported in both forms.
    assert metrics["fwhm_arcsec"] == pytest.approx(5.0)
    assert metrics["sigma_arcsec"] == pytest.approx(5.0 / GAUSSIAN_FWHM_TO_SIGMA)


@pytest.mark.unit
def test_psf_aperture_metrics_scale_with_brightness_and_separation() -> None:
    """A five-magnitude-fainter contaminant contributes ~1%; a distant one ~0%."""
    model = ContaminationModelConfig(mode="gaussian_psf", gaussian_fwhm_arcsec=5.0)

    faint = psf_aperture_metrics(10.0, np.array([15.0]), np.array([True]), np.array([0.0]), model, 10.0)
    assert faint is not None
    assert faint["contamination_ratio"] == pytest.approx(0.01, abs=1e-6)
    assert faint["target_purity"] == pytest.approx(1.0 / 1.01, abs=1e-6)

    distant = psf_aperture_metrics(10.0, np.array([10.0]), np.array([True]), np.array([30.0]), model, 10.0)
    assert distant is not None
    assert distant["contamination_ratio"] == pytest.approx(0.0, abs=1e-4)
    assert distant["target_purity"] == pytest.approx(1.0, abs=1e-4)


@pytest.mark.unit
def test_psf_aperture_metrics_only_apply_to_gaussian_psf_models() -> None:
    """Non-PSF models (or no contaminants) return the expected values."""
    top_hat = ContaminationModelConfig(mode="top_hat")
    assert psf_aperture_metrics(10.0, np.array([10.0]), np.array([True]), np.array([0.0]), top_hat, 10.0) is None

    model = ContaminationModelConfig(mode="gaussian_psf", gaussian_fwhm_arcsec=5.0)
    empty = psf_aperture_metrics(10.0, np.empty(0), np.empty(0, dtype=bool), np.empty(0), model, 10.0)
    assert empty is not None
    assert empty["contamination_ratio"] == 0.0
    assert empty["target_purity"] == 1.0


@pytest.mark.regression
def test_top_hat_ignores_stale_psf_fields_when_deriving_the_influence_radius() -> None:
    """top_hat must not inherit an influence radius from leftover FWHM/sigma values.

    Deriving one anyway pushed the radius past the index build radius, which
    silently switched the query to a full-catalogue neighbour recomputation per
    target: a run that takes seconds took hours.
    """
    stale = ContaminationModelConfig(mode="top_hat", gaussian_fwhm_arcsec=300.0, influence_sigma=3.0)
    assert stale.influence_radius_arcsec is None

    psf = ContaminationModelConfig(mode="gaussian_psf", gaussian_fwhm_arcsec=300.0, influence_sigma=3.0)
    assert psf.influence_radius_arcsec == pytest.approx(3.0 * 300.0 / GAUSSIAN_FWHM_TO_SIGMA)


@pytest.mark.unit
def test_influence_provider_matches_an_exhaustive_search() -> None:
    """The declination-band filter must be exact, not merely close.

    Separation is never smaller than the declination difference, so the band can
    only exclude sources that are provably outside the radius.
    """
    from photo_cat.query_contamination_from_index import separation_arcsec

    rng = np.random.default_rng(0)
    ra = rng.uniform(0.0, 360.0, 2000)
    dec = np.degrees(np.arcsin(rng.uniform(-1.0, 1.0, 2000)))
    radius = 3600.0

    provider = make_influence_neighbor_provider(ra, dec, radius)
    for target in (1, 500, 1999):
        index = target - 1
        separations = separation_arcsec(float(ra[index]), float(dec[index]), ra, dec)
        expected = np.flatnonzero(separations <= radius)
        expected = expected[expected != index] + 1
        assert np.array_equal(np.sort(provider(target)), np.sort(expected))


@pytest.mark.unit
def test_influence_neighbor_provider_recomputes_per_target_from_the_catalogue() -> None:
    """The provider finds neighbours out to the influence radius directly from RA/Dec."""
    from photo_cat.query_contamination_from_index import make_influence_neighbor_provider

    # Target at (0, 0); one neighbour ~36" east (0.01 deg), one ~360" east (0.1 deg).
    ra = np.array([0.0, 0.01, 0.1])
    dec = np.array([0.0, 0.0, 0.0])

    near_only = make_influence_neighbor_provider(ra, dec, influence_radius_arcsec=60.0)
    # internal ids are catalogue index + 1; self (index 0) is excluded.
    assert near_only(1).tolist() == [2]

    both = make_influence_neighbor_provider(ra, dec, influence_radius_arcsec=400.0)
    assert sorted(both(1).tolist()) == [2, 3]
