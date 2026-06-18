# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Shared pytest fixtures for PHOTO-CAT behavioural and unit tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pytest


@dataclass(frozen=True)
class SampleInputs:
    """Paths for a temporary copy of the bundled catalogue and targets fixtures."""

    catalog_path: Path
    targets_path: Path


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Return the source checkout root used to read bundled test data."""
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def sample_inputs(tmp_path: Path, project_root: Path) -> SampleInputs:
    """Copy bundled CSV fixtures so tests never write inside the checkout."""
    catalog_path = tmp_path / "example_catalog.csv"
    targets_path = tmp_path / "example_targets.csv"

    catalog_path.write_text(
        (project_root / "data" / "example_catalog.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    targets_path.write_text(
        (project_root / "data" / "example_targets.csv").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    return SampleInputs(catalog_path, targets_path)


@pytest.fixture
def config_text() -> str:
    """Provide a minimal valid configuration template with local relative paths."""
    return """
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
  replace_running_pipeline: true
"""


@pytest.fixture
def write_config(tmp_path: Path, config_text: str) -> Callable[[str | None], Path]:
    """Return a helper that writes a config and the minimal input CSV files it references."""
    def _write_config(text: str | None = None) -> Path:
        (tmp_path / "catalog.csv").write_text(
            "source_id,ra,dec,phot_g_mean_mag\n1001,10.0,20.0,10.0\n",
            encoding="utf-8",
        )
        (tmp_path / "targets.csv").write_text("source_id\n1001\n", encoding="utf-8")
        config_path = tmp_path / "config.yaml"
        config_path.write_text(text or config_text, encoding="utf-8")
        return config_path

    return _write_config


@pytest.fixture
def cli_config_text(config_text: str) -> str:
    """Provide a valid CLI override baseline including the legacy column list."""
    return config_text.replace(
        "    columns:\n",
        "    usecolumns:\n      - source_id\n      - ra\n      - dec\n      - phot_g_mean_mag\n    columns:\n",
    )


@pytest.fixture
def write_minimal_index(tmp_path: Path) -> Callable[[], Path]:
    """Return an isolated index directory with numeric and special source-ID mappings."""
    def _write_minimal_index() -> Path:
        index_dir = tmp_path / "index"
        index_dir.mkdir()

        np.save(index_dir / "offsets.npy", np.array([0, 0, 0, 0], dtype=np.int64))
        np.array([], dtype=np.int64).tofile(index_dir / "neighbors_ids.bin")
        np.save(index_dir / "ra.npy", np.array([10.0, 11.0, 12.0], dtype=np.float64))
        np.save(index_dir / "dec.npy", np.array([20.0, 21.0, 22.0], dtype=np.float64))
        np.save(index_dir / "phot_g_mean_mag.npy", np.array([10.0, 11.0, 12.0], dtype=np.float64))
        np.save(index_dir / "real_ids_int.npy", np.array([1001, 1002, -1], dtype=np.int64))
        np.savez_compressed(
            index_dir / "special_ids.npz",
            internal_ids=np.array([3], dtype=np.int64),
            names=np.array(["HD 216608A"], dtype=object),
        )

        return index_dir

    return _write_minimal_index
