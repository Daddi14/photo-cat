# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for the bundled scientific sample workflow."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from photo_cat import build_neighbors_index, query_contamination_from_index


def write_pipeline_config(tmp_path: Path, sample_inputs) -> Path:
    """Write the smallest full pipeline config using isolated copies of bundled sample data."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
build_neighbors_index:
  io:
    input_catalog: {sample_inputs.catalog_path.as_posix()}
    out_dir: {(tmp_path / 'output').as_posix()}
    KDTREE_FILENAME: ckdtree.pkl
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Protect public scientific output while internal build/query functions are refactored."""
    config_path = write_pipeline_config(tmp_path, sample_inputs)
    monkeypatch.setenv("PHOTO_CAT_CONFIG", str(config_path))
    monkeypatch.setenv("PHOTO_CAT_COMPACT_LOG", "1")

    assert build_neighbors_index.main() == 0
    assert query_contamination_from_index.main() == 0

    result_files = sorted((tmp_path / "output" / "output").glob("*.json"))
    assert len(result_files) == 1

    results = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert [row["source_id"] for row in results] == ["1001", "HD 216608A"]

    numeric_target = results[0]
    assert numeric_target["num_contaminants"] == 1
    assert numeric_target["flux_fraction_extra"] == pytest.approx(15.85)
    assert numeric_target["contaminants"][0]["source_id"] == "1002"
    assert numeric_target["contaminants"][0]["sep_arcsec"] == pytest.approx(16.914467, rel=1e-6)

    string_target = results[1]
    assert string_target["num_contaminants"] == 1
    assert string_target["flux_fraction_extra"] == pytest.approx(1.58)
    assert string_target["contaminants"][0]["source_id"] == "HD 216608B"
    assert string_target["contaminants"][0]["sep_arcsec"] == pytest.approx(35.863009, rel=1e-6)
