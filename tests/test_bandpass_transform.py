# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for provenance-tracked empirical catalogue-to-mission band transformations."""

from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pytest

from photo_cat.bandpass_transform import (
    STATUS_EXTRAPOLATED,
    STATUS_MISSING_INPUT,
    STATUS_OUTSIDE_VALIDITY,
    STATUS_VALID,
    load_bandpass_profile,
    transform_magnitudes,
)
from photo_cat.load_config import ContaminationModelConfig
from photo_cat import build_neighbors_index, query_contamination_from_index
from photo_cat.query_contamination_from_index import process_target
from photo_cat.result_products import summarize_results


def write_profile(tmp_path: Path, *, out_of_range: str = "null") -> Path:
    """Write a compact valid colour-polynomial profile."""
    path = tmp_path / "mission_band.yaml"
    path.write_text(
        "schema_version: 1\n"
        "name: Example mission from Gaia\n"
        "output_band: mission_blue\n"
        "base_band: gaia_g\n"
        "color_bands: [gaia_bp, gaia_rp]\n"
        "coefficients: [0.1, 0.2]\n"
        "validity:\n"
        "  color_min: -0.5\n"
        "  color_max: 1.5\n"
        "  base_magnitude_min: 5\n"
        "  base_magnitude_max: 15\n"
        f"out_of_range: {out_of_range}\n"
        "reference: Example calibration, replace before scientific use\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.unit
def test_bandpass_profile_transforms_valid_rows_and_nulls_invalid_rows(tmp_path: Path) -> None:
    """The polynomial convention and validity statuses must be scientifically explicit."""
    profile = load_bandpass_profile(write_profile(tmp_path))
    result = transform_magnitudes(
        profile,
        {
            "gaia_g": np.array([10.0, 10.0, np.nan]),
            "gaia_bp": np.array([11.0, 13.0, 12.0]),
            "gaia_rp": np.array([10.0, 10.0, 11.0]),
        },
    )

    assert result.magnitudes[0] == pytest.approx(10.3)
    assert np.isnan(result.magnitudes[1:]).all()
    assert result.status_codes.tolist() == [STATUS_VALID, STATUS_OUTSIDE_VALIDITY, STATUS_MISSING_INPUT]
    assert profile.metadata()["profile_sha256"]
    assert profile.required_bands == ("gaia_g", "gaia_bp", "gaia_rp")


@pytest.mark.unit
def test_bandpass_profile_can_explicitly_extrapolate(tmp_path: Path) -> None:
    """Out-of-range extrapolation is opt-in and must remain marked per source."""
    profile = load_bandpass_profile(write_profile(tmp_path, out_of_range="extrapolate"))
    result = transform_magnitudes(
        profile,
        {
            "gaia_g": np.array([10.0]),
            "gaia_bp": np.array([13.0]),
            "gaia_rp": np.array([10.0]),
        },
    )

    assert result.magnitudes[0] == pytest.approx(10.7)
    assert result.status_codes.tolist() == [STATUS_EXTRAPOLATED]


@pytest.mark.unit
def test_bandpass_profile_rejects_invalid_schema_and_missing_arrays(tmp_path: Path) -> None:
    """Incomplete calibration definitions must fail before a query publishes results."""
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("schema_version: 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="schema_version"):
        load_bandpass_profile(invalid)

    profile = load_bandpass_profile(write_profile(tmp_path))
    with pytest.raises(ValueError, match="unavailable magnitude bands"):
        transform_magnitudes(profile, {"gaia_g": np.array([10.0])})


@pytest.mark.unit
def test_transformed_band_is_reported_alongside_direct_catalogue_metrics(tmp_path: Path) -> None:
    """A mission-band estimate must be additive and carry its target validity status."""
    profile = load_bandpass_profile(write_profile(tmp_path))
    transformed = transform_magnitudes(
        profile,
        {
            "gaia_g": np.array([10.0, 11.0]),
            "gaia_bp": np.array([11.0, 12.0]),
            "gaia_rp": np.array([10.0, 11.0]),
        },
    )
    result = process_target(
        internal_target=1,
        offsets=np.array([0, 1, 1]),
        neighbors_mm=np.array([2]),
        ra=np.array([10.0, 10.0]),
        dec=np.array([20.0, 20.0]),
        gmag=np.array([10.0, 11.0]),
        real_ids_int=np.array([1001, 1002]),
        internal_to_special_name={},
        field_of_view_arcsec=47.0,
        delta_mag=5.0,
        neighbor_separations_mm=np.array([1.0]),
        contamination_model=ContaminationModelConfig(),
        magnitude_arrays={"gaia_g": np.array([10.0, 11.0]), profile.output_band: transformed.magnitudes},
        bandpass_status_codes=transformed.status_codes,
        bandpass_output_band=profile.output_band,
        bandpass_profile_name=profile.name,
    )

    assert result is not None
    assert result["flux_fraction_selected_by_band"]["gaia_g"] == pytest.approx(39.81)
    assert result["flux_fraction_selected_by_band"]["mission_blue"] == pytest.approx(39.81)
    assert result["flux_fraction_selected_transformed"] == pytest.approx(39.81)
    assert result["bandpass_transform_status"] == "valid"
    assert result["bandpass_transform_profile"] == profile.name
    assert result["target_magnitudes_by_band"]["mission_blue"] == pytest.approx(10.3)
    assert result["contaminants"][0]["magnitudes_by_band"]["mission_blue"] == pytest.approx(11.3)


@pytest.mark.regression
def test_pipeline_applies_profile_and_records_provenance(tmp_path: Path) -> None:
    """A complete build/query run should publish mission-band metrics and profile provenance."""
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "source_id,ra,dec,phot_g_mean_mag,phot_bp_mean_mag,phot_rp_mean_mag\n"
        "1,10.0,20.0,10.0,11.0,10.0\n"
        "2,10.001,20.0,11.0,13.0,11.0\n",
        encoding="utf-8",
    )
    targets_path = tmp_path / "targets.csv"
    targets_path.write_text("source_id\n1\n", encoding="utf-8")
    profile_path = write_profile(tmp_path)
    profile_path.write_text(
        profile_path.read_text(encoding="utf-8").replace("color_max: 1.5", "color_max: 3.0"),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "build_neighbors_index:\n"
        "  io:\n"
        "    input_catalog: catalog.csv\n"
        "    out_dir: index\n"
        "    columns: {source_id: source_id, ra: ra, dec: dec, phot_g_mean_mag: phot_g_mean_mag}\n"
        "    magnitude_columns: {gaia_bp: phot_bp_mean_mag, gaia_rp: phot_rp_mean_mag}\n"
        "  settings: {use_dask: false, calculate_separations: true, max_radius_arcsec: 120, chunk_size: 2, buffer_flush_interval: 1}\n"
        "query_contamination_from_index:\n"
        "  io: {INDEX_DIR: index, TARGETS_INPUT: targets.csv, targets: [], target_source_id_column: source_id}\n"
        "  settings:\n"
        "    field_of_view_arcsec: 47\n"
        "    delta_mag: 5\n"
        "    contamination_bands: [gaia_g]\n"
        f"    bandpass_transform_file: {profile_path.name}\n"
        "execution: {run_build: true, run_query: true, replace_running_pipeline: true}\n",
        encoding="utf-8",
    )

    assert build_neighbors_index.main(config_path) == 0
    assert query_contamination_from_index.main(config_path) == 0
    result_path = next((tmp_path / "index" / "results").glob("*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))[0]
    metadata_path = next((tmp_path / "index" / "results" / "metadata").glob("*.json"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert result["flux_fraction_selected_by_band"]["gaia_g"] == pytest.approx(39.81)
    assert result["flux_fraction_selected_by_band"]["mission_blue"] == pytest.approx(33.11)
    assert result["flux_fraction_total_weighted_transformed"] == pytest.approx(33.11)
    assert result["bandpass_transform_status"] == "valid"
    assert result["target_magnitudes_by_band"]["mission_blue"] == pytest.approx(10.3)
    assert result["contaminants"][0]["magnitudes_by_band"]["mission_blue"] == pytest.approx(11.5)
    assert metadata["bandpass_transform"]["profile_sha256"]
    assert metadata["bandpass_transform"]["output_band"] == "mission_blue"
    summary = summarize_results([result])
    assert summary["transformed_total_weighted_flux_fraction_percent"]["mean"] == pytest.approx(33.11)
