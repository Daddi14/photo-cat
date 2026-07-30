# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for the bundled scientific sample workflow."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from photo_cat import build_neighbors_index, query_contamination_from_index
from photo_cat import __version__
from photo_cat.photometry.conversion import convert_magnitudes


def write_pipeline_config(tmp_path: Path, sample_inputs) -> Path:
    """Write the smallest full pipeline config using isolated copies of bundled sample data."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
build_neighbors_index:
  io:
    input_catalog: {sample_inputs.catalog_path.as_posix()}
    out_dir: {(tmp_path / 'output').as_posix()}
    columns:
      source_id: source_id
      ra: ra
      dec: dec
      phot_g_mean_mag: phot_g_mean_mag
  settings:
    use_dask: false
    calculate_separations: false
    max_radius_arcsec: 120.0
    chunk_size: 2
    buffer_flush_interval: 1
query_contamination_from_index:
  io:
    INDEX_DIR: {(tmp_path / 'output').as_posix()}
    TARGETS_INPUT: {sample_inputs.targets_path.as_posix()}
    targets: []
    target_source_id_column: source_id
  settings:
    field_of_view_arcsec: 47.0
    delta_mag: 5.0
execution:
  run_build: true
  run_query: true
""".strip() + "\n",
        encoding="utf-8",
    )
    return config_path


@pytest.mark.regression
def test_sample_pipeline_builds_index_and_queries_expected_results(
    tmp_path: Path,
    sample_inputs,
) -> None:
    """Protect public scientific output while internal build/query functions are refactored."""
    config_path = write_pipeline_config(tmp_path, sample_inputs)
    assert build_neighbors_index.main(config_path) == 0
    assert query_contamination_from_index.main(config_path) == 0

    result_files = sorted((tmp_path / "output" / "results").glob("*.json"))
    assert len(result_files) == 1

    results = json.loads(result_files[0].read_text(encoding="utf-8"))
    metadata_files = sorted((tmp_path / "output" / "results" / "metadata").glob("*.json"))
    assert len(metadata_files) == 1
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    assert metadata["photo_cat_version"] == __version__
    assert metadata["processed_targets"] == 2
    assert metadata["contamination_model"]["kind"] == "catalogue_aperture_flux_ratio"

    assert [row["source_id"] for row in results] == ["1001", "HD 216608A"]

    numeric_target = results[0]
    assert numeric_target["num_contaminants"] == 1
    assert numeric_target["num_contaminants_selected"] == 1
    assert numeric_target["num_neighbors_in_radius"] == 1
    assert numeric_target["flux_fraction_selected"] == pytest.approx(15.85)
    assert numeric_target["flux_fraction_all_neighbors"] == pytest.approx(15.85)
    assert numeric_target["flux_fraction_extra"] == pytest.approx(15.85)
    assert numeric_target["contaminants"][0]["source_id"] == "1002"
    assert numeric_target["contaminants"][0]["sep_arcsec"] == pytest.approx(16.914467, rel=1e-6)

    string_target = results[1]
    assert string_target["num_contaminants"] == 1
    assert string_target["flux_fraction_extra"] == pytest.approx(1.58)
    assert string_target["contaminants"][0]["source_id"] == "HD 216608B"
    assert string_target["contaminants"][0]["sep_arcsec"] == pytest.approx(35.863009, rel=1e-6)


@pytest.mark.regression
def test_output_band_controls_selection_and_prefers_nominal_catalogue_magnitudes(tmp_path: Path) -> None:
    """An exact BP measurement must drive every primary result instead of Gaia G or a conversion."""
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "source_id,ra,dec,phot_g_mean_mag,phot_bp_mean_mag,phot_rp_mean_mag\n"
        "1,10.000,0.0,10.0,10.0,9.0\n"
        # Passes delta_mag=5 in G, but not in the selected BP output band.
        "2,10.005,0.0,14.0,16.0,15.0\n"
        # Fails in G, but passes in BP and therefore is the actual contaminant.
        "3,10.010,0.0,16.0,14.0,13.0\n",
        encoding="utf-8",
    )
    targets_path = tmp_path / "targets.csv"
    targets_path.write_text("source_id\n1\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
build_neighbors_index:
  io:
    input_catalog: {catalog_path.as_posix()}
    out_dir: {output_dir.as_posix()}
    columns:
      source_id: source_id
      ra: ra
      dec: dec
      phot_g_mean_mag: phot_g_mean_mag
    magnitude_columns:
      gaia_g: phot_g_mean_mag
      gaia_bp: phot_bp_mean_mag
      gaia_rp: phot_rp_mean_mag
  settings:
    use_dask: false
    calculate_separations: false
    max_radius_arcsec: 120.0
    chunk_size: 2
    buffer_flush_interval: 1
query_contamination_from_index:
  io:
    INDEX_DIR: {output_dir.as_posix()}
    TARGETS_INPUT: {targets_path.as_posix()}
    targets: []
    target_source_id_column: source_id
  settings:
    field_of_view_arcsec: 47.0
    delta_mag: 5.0
    contamination_bands: [gaia_g]
    photometric_conversion:
      output_band: gaia_bp
      conversion_method: phoenix
      catalog: gaia_dr3
execution:
  run_build: true
  run_query: true
""".strip() + "\n",
        encoding="utf-8",
    )

    assert build_neighbors_index.main(config_path) == 0
    assert query_contamination_from_index.main(config_path) == 0

    result_path = next((output_dir / "results").glob("*.json"))
    target = json.loads(result_path.read_text(encoding="utf-8"))[0]
    assert target["magnitude_band"] == "gaia_bp"
    assert target["magnitude_source"] == "catalogue"
    assert target["magnitude"] == pytest.approx(10.0)
    assert "phot_g_mean_mag" not in target
    assert target["output_band"] == "gaia_bp"
    assert target["conversion_method"] is None
    assert target["conversion_status"] is None
    assert target["effective_temperature"] is None
    assert target["converted_target_flux"] is None
    assert "converted_gaia_bp" not in target["flux_fraction_selected_by_band"]

    assert target["num_contaminants"] == 1
    assert target["flux_fraction_selected"] == pytest.approx(2.51)
    contaminant = target["contaminants"][0]
    assert contaminant["source_id"] == "3"
    assert contaminant["magnitude"] == pytest.approx(14.0)
    assert contaminant["magnitude_band"] == "gaia_bp"
    assert contaminant["magnitude_source"] == "catalogue"
    assert "phot_g_mean_mag" not in contaminant

    metadata_path = next((output_dir / "results" / "metadata").glob("*.json"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["photometric_conversion"]["conversion_applied"] is False
    assert metadata["photometric_conversion"]["catalog_band"] == "gaia_bp"


@pytest.mark.regression
def test_converted_mission_band_controls_the_delta_magnitude_cut(tmp_path: Path) -> None:
    """When no nominal output band exists, selection must use converted rather than G magnitudes."""
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "source_id,ra,dec,phot_g_mean_mag,phot_bp_mean_mag,phot_rp_mean_mag\n"
        "1,10.000,0.0,10.0,10.4,9.6\n"
        # G difference is 5 (selected in G), but the blue colour makes it too faint in TESS.
        "2,10.005,0.0,15.0,14.9,15.1\n"
        # G difference is 5.5 (rejected in G), but the red colour brings it inside the TESS cut.
        "3,10.010,0.0,15.5,16.75,14.25\n",
        encoding="utf-8",
    )
    targets_path = tmp_path / "targets.csv"
    targets_path.write_text("source_id\n1\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
build_neighbors_index:
  io:
    input_catalog: {catalog_path.as_posix()}
    out_dir: {output_dir.as_posix()}
    columns:
      source_id: source_id
      ra: ra
      dec: dec
      phot_g_mean_mag: phot_g_mean_mag
    magnitude_columns:
      gaia_g: phot_g_mean_mag
      gaia_bp: phot_bp_mean_mag
      gaia_rp: phot_rp_mean_mag
  settings:
    use_dask: false
    calculate_separations: false
    max_radius_arcsec: 120.0
    chunk_size: 2
    buffer_flush_interval: 1
query_contamination_from_index:
  io:
    INDEX_DIR: {output_dir.as_posix()}
    TARGETS_INPUT: {targets_path.as_posix()}
    targets: []
    target_source_id_column: source_id
  settings:
    field_of_view_arcsec: 47.0
    delta_mag: 5.0
    contamination_bands: [gaia_g]
    photometric_conversion:
      output_band: tess
      conversion_method: blackbody
      catalog: gaia_dr3
execution:
  run_build: true
  run_query: true
""".strip() + "\n",
        encoding="utf-8",
    )

    expected = convert_magnitudes(
        {
            "gaia_g": np.array([10.0, 15.0, 15.5]),
            "gaia_bp": np.array([10.4, 14.9, 16.75]),
            "gaia_rp": np.array([9.6, 15.1, 14.25]),
        },
        "tess",
    ).out_magnitudes
    assert expected[1] - expected[0] > 5.0
    assert expected[2] - expected[0] < 5.0

    assert build_neighbors_index.main(config_path) == 0
    assert query_contamination_from_index.main(config_path) == 0

    result_path = next((output_dir / "results").glob("*.json"))
    target = json.loads(result_path.read_text(encoding="utf-8"))[0]
    assert target["magnitude_band"] == "tess"
    assert target["magnitude_source"] == "converted"
    assert target["magnitude"] == pytest.approx(expected[0])
    assert target["num_contaminants"] == 1
    assert target["contaminants"][0]["source_id"] == "3"
    assert target["contaminants"][0]["magnitude"] == pytest.approx(expected[2])
