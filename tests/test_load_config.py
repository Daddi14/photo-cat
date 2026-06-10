# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for PHOTO-CAT configuration loading."""

from pathlib import Path

import pytest

from photo_cat.load_config import BuildConfig, QueryConfig, load_config, resolve_config_path


CONFIG_TEXT = """
build_neighbors_index:
  io:
    input_catalog: catalog.csv
    out_dir: output
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
"""


def write_config_fixture(tmp_path: Path) -> Path:
    (tmp_path / "catalog.csv").write_text(
        "source_id,ra,dec,phot_g_mean_mag\n1001,10.0,20.0,10.0\n",
        encoding="utf-8",
    )
    (tmp_path / "targets.csv").write_text("source_id\n1001\n", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(CONFIG_TEXT, encoding="utf-8")
    return config_path


def test_resolve_config_path_prefers_runtime_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = write_config_fixture(tmp_path)
    monkeypatch.setenv("PHOTO_CAT_CONFIG", str(config_path))

    assert resolve_config_path() == config_path.resolve()


def test_load_build_config_resolves_paths(tmp_path: Path) -> None:
    config_path = write_config_fixture(tmp_path)
    config = load_config("build_neighbors_index", str(config_path))

    assert isinstance(config, BuildConfig)
    assert config.input_catalog == str((tmp_path / "catalog.csv").resolve())
    assert config.out_dir == str((tmp_path / "output").resolve())
    assert config.use_dask is False
    assert config.usecolumns == ["source_id", "ra", "dec", "phot_g_mean_mag"]


def test_load_query_config_resolves_paths(tmp_path: Path) -> None:
    config_path = write_config_fixture(tmp_path)
    config = load_config("query_contamination_from_index", str(config_path))

    assert isinstance(config, QueryConfig)
    assert config.INDEX_DIR == str((tmp_path / "output").resolve())
    assert config.TARGETS_INPUT == str((tmp_path / "targets.csv").resolve())
    assert config.field_of_view_arcsec == 47.0
    assert config.delta_mag == 5.0


def test_load_config_rejects_unknown_section(tmp_path: Path) -> None:
    config_path = write_config_fixture(tmp_path)

    with pytest.raises(ValueError, match="Unknown configuration section"):
        load_config("not_a_real_section", str(config_path))
