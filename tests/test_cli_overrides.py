# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for PHOTO-CAT CLI runtime configuration overrides."""

from __future__ import annotations

from pathlib import Path

import yaml

from photo_cat import cli
from photo_cat.cli_overrides import RuntimeConfigOverride, collect_overrides, load_base_config


BASE_CONFIG = """
build_neighbors_index:
  io:
    input_catalog: catalog.csv
    out_dir: output
    KDTREE_FILENAME: ckdtree.pkl
    usecolumns:
      - source_id
      - ra
      - dec
      - phot_g_mean_mag
    columns:
      source_id: source_id
      ra: ra
      dec: dec
      phot_g_mean_mag: phot_g_mean_mag
  settings:
    use_dask: true
    calculate_separations: false
    max_radius_arcsec: 120.0
    chunk_size: 10000
    buffer_flush_interval: 200
query_contamination_from_index:
  io:
    INDEX_DIR: output
    TARGETS_INPUT: targets.csv
    targets: []
    target_source_id_column: source_id
  settings:
    field_of_view_arcsec: 47.0
    delta_mag: 5.0
execution:
  run_build: true
  run_query: true
  replace_running_pipeline: true
"""


def write_config(tmp_path: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(BASE_CONFIG, encoding="utf-8")
    return config_path


def test_cli_run_accepts_all_override_groups(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    parser = cli.build_parser()

    args = parser.parse_args([
        "run",
        "--config", "config.yaml",
        "--input-catalog", "catalog.csv",
        "--out-dir", "output/run",
        "--kdtree-filename", "tree.pkl",
        "--usecolumns", "id,RA,DEC,G",
        "--catalog-source-id-column", "id",
        "--ra-column", "RA",
        "--dec-column", "DEC",
        "--mag-column", "G",
        "--no-use-dask",
        "--calculate-separations",
        "--max-radius-arcsec", "180",
        "--chunk-size", "500",
        "--buffer-flush-interval", "25",
        "--index-dir", "output/run",
        "--no-targets-input",
        "--targets", "1001,HD 216608A",
        "--target-source-id-column", "id",
        "--field-of-view-arcsec", "60",
        "--delta-mag", "4",
        "--run-build",
        "--no-run-query",
        "--no-replace-running-pipeline",
    ])

    overrides = collect_overrides(args)

    assert overrides["input_catalog"] == str((tmp_path / "catalog.csv").resolve())
    assert overrides["out_dir"] == str((tmp_path / "output" / "run").resolve())
    assert overrides["kdtree_filename"] == "tree.pkl"
    assert overrides["usecolumns"] == ["id", "RA", "DEC", "G"]
    assert overrides["catalog_source_id_column"] == "id"
    assert overrides["ra_column"] == "RA"
    assert overrides["dec_column"] == "DEC"
    assert overrides["phot_g_mean_mag_column"] == "G"
    assert overrides["use_dask"] is False
    assert overrides["calculate_separations"] is True
    assert overrides["max_radius_arcsec"] == 180.0
    assert overrides["chunk_size"] == 500
    assert overrides["buffer_flush_interval"] == 25
    assert overrides["index_dir"] == str((tmp_path / "output" / "run").resolve())
    assert overrides["targets_input"] is None
    assert overrides["targets"] == ["1001", "HD 216608A"]
    assert overrides["target_source_id_column"] == "id"
    assert overrides["field_of_view_arcsec"] == 60.0
    assert overrides["delta_mag"] == 4.0
    assert overrides["run_build"] is True
    assert overrides["run_query"] is False
    assert overrides["replace_running_pipeline"] is False


def test_runtime_config_override_writes_nested_yaml_values(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = write_config(tmp_path)

    parser = cli.build_parser()
    args = parser.parse_args([
        "run",
        "--config", str(config_path),
        "--input-catalog", "catalog_override.csv",
        "--targets-input", "targets_override.csv",
        "--out-dir", "output/override",
        "--index-dir", "output/override",
        "--catalog-source-id-column", "id",
        "--ra-column", "RAJ2000",
        "--dec-column", "DEJ2000",
        "--mag-column", "Gmag",
        "--field-of-view-arcsec", "75",
        "--delta-mag", "3.5",
        "--no-use-dask",
        "--no-run-build",
        "--run-query",
    ])

    overrides = collect_overrides(args)

    with RuntimeConfigOverride(config_path, overrides) as runtime_config_path:
        assert runtime_config_path is not None
        runtime_config = yaml.safe_load(runtime_config_path.read_text(encoding="utf-8"))

        assert runtime_config["build_neighbors_index"]["io"]["input_catalog"] == str((tmp_path / "catalog_override.csv").resolve())
        assert runtime_config["build_neighbors_index"]["io"]["out_dir"] == str((tmp_path / "output" / "override").resolve())
        assert runtime_config["query_contamination_from_index"]["io"]["TARGETS_INPUT"] == str((tmp_path / "targets_override.csv").resolve())
        assert runtime_config["query_contamination_from_index"]["io"]["INDEX_DIR"] == str((tmp_path / "output" / "override").resolve())

        columns = runtime_config["build_neighbors_index"]["io"]["columns"]
        assert columns["source_id"] == "id"
        assert columns["ra"] == "RAJ2000"
        assert columns["dec"] == "DEJ2000"
        assert columns["phot_g_mean_mag"] == "Gmag"
        assert runtime_config["build_neighbors_index"]["io"]["usecolumns"] == ["id", "RAJ2000", "DEJ2000", "Gmag"]

        assert runtime_config["query_contamination_from_index"]["settings"]["field_of_view_arcsec"] == 75.0
        assert runtime_config["query_contamination_from_index"]["settings"]["delta_mag"] == 3.5
        assert runtime_config["build_neighbors_index"]["settings"]["use_dask"] is False
        assert runtime_config["execution"]["run_build"] is False
        assert runtime_config["execution"]["run_query"] is True

    assert not runtime_config_path.exists()


def test_runtime_config_override_can_start_from_defaults(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    missing_config = tmp_path / "missing.yaml"

    parser = cli.build_parser()
    args = parser.parse_args([
        "run",
        "--config", str(missing_config),
        "--input-catalog", "catalog.csv",
        "--no-targets-input",
        "--targets", "1001,1002",
    ])

    overrides = collect_overrides(args)

    with RuntimeConfigOverride(missing_config, overrides) as runtime_config_path:
        assert runtime_config_path is not None
        runtime_config = yaml.safe_load(runtime_config_path.read_text(encoding="utf-8"))

        assert runtime_config["build_neighbors_index"]["io"]["input_catalog"] == str((tmp_path / "catalog.csv").resolve())
        assert runtime_config["query_contamination_from_index"]["io"]["TARGETS_INPUT"] is None
        assert runtime_config["query_contamination_from_index"]["io"]["targets"] == ["1001", "1002"]


def test_load_base_config_uses_defaults_when_config_is_missing(tmp_path: Path) -> None:
    config, config_dir = load_base_config(tmp_path / "missing.yaml")

    assert config_dir == Path.cwd().resolve()
    assert config["build_neighbors_index"]["io"]["columns"]["ra"] == "ra"
    assert config["query_contamination_from_index"]["settings"]["delta_mag"] == 5.0
