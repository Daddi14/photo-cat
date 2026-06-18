# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for centralised path-resolution and query-index path policies."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from photo_cat.path_policy import (
    index_paths,
    query_output_json_path,
    resolve_config_file_path,
    resolve_user_path,
    validate_index_paths,
)
from photo_cat.query_contamination_from_index import load_catalog_arrays


@pytest.mark.unit
def test_resolve_user_path_anchors_relative_values_to_the_explicit_base_directory(tmp_path: Path) -> None:
    """Config and CLI callers can choose their own base directory without changing process cwd."""
    config_dir = tmp_path / "configuration"
    config_dir.mkdir()

    resolved_path = resolve_user_path("inputs/catalog.csv", config_dir)

    assert resolved_path == (config_dir / "inputs" / "catalog.csv").resolve()


@pytest.mark.unit
def test_resolve_config_file_path_prefers_explicit_path_over_environment_and_default(tmp_path: Path) -> None:
    """An explicit --config selection must remain authoritative over runtime environment state."""
    explicit_path = tmp_path / "explicit.yaml"
    environment_path = tmp_path / "environment.yaml"
    default_path = tmp_path / "default.yaml"

    resolved_path = resolve_config_file_path(
        explicit_path.name,
        base_dir=tmp_path,
        default_path=default_path,
        environment_path=str(environment_path),
    )

    assert resolved_path == explicit_path.resolve()


@pytest.mark.unit
def test_validate_index_paths_returns_named_files_for_a_complete_index(write_minimal_index) -> None:
    """Query execution receives a named path object instead of reconstructing index filenames repeatedly."""
    root = write_minimal_index()

    paths = validate_index_paths(index_paths(root))

    assert paths.root == root.resolve()
    assert paths.offsets == root / "offsets.npy"
    assert paths.neighbors_ids == root / "neighbors_ids.bin"
    assert paths.output_dir == root / "output"


@pytest.mark.unit
def test_query_output_path_stays_inside_the_index_output_directory(write_minimal_index) -> None:
    """Timestamped JSON results must remain under INDEX_DIR/output regardless of target-file location."""
    root = write_minimal_index()
    target_path = root.parent / "targets.csv"
    target_path.write_text("source_id\n1001\n", encoding="utf-8")

    result_path = query_output_json_path(
        index_paths(root),
        str(target_path),
        47.0,
        5.0,
        now=datetime(2026, 6, 18, 12, 34, 56),
    )

    assert result_path.parent == root / "output"
    assert result_path.name == "targets_FoV47_dmag5_20260618_1234.json"


@pytest.mark.unit
def test_load_catalog_arrays_accepts_prevalidated_index_paths(write_minimal_index) -> None:
    """Numerical query loading can consume validated paths without repeating path-resolution policy."""
    paths = validate_index_paths(index_paths(write_minimal_index()))

    *_, targets_internal = load_catalog_arrays(paths, targets=["1001"])

    assert targets_internal == [1]


@pytest.mark.unit
def test_ensure_directory_creates_a_validated_runtime_folder_only_when_called(tmp_path: Path) -> None:
    """Runtime directory creation is explicit and remains separate from config/path parsing."""
    from photo_cat.path_policy import ensure_directory

    output_dir = tmp_path / "runtime-output"

    assert not output_dir.exists()
    assert ensure_directory(output_dir, "test output") == output_dir
    assert output_dir.is_dir()
