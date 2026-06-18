# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for user-facing catalogue, target, index, and output-path validation."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from photo_cat.build_neighbors_index import validate_required_columns
from photo_cat.load_config import load_config
from photo_cat.query_contamination_from_index import (
    create_output_json_path,
    validate_index_directory,
    validate_target_column,
)


@pytest.mark.unit
def test_catalog_column_error_lists_missing_column_and_case_hint(tmp_path: Path) -> None:
    """A CSV header case mismatch must name the missing configured column and plausible correction."""
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "source_id,RA,dec,phot_g_mean_mag\n1001,10.0,20.0,11.0\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Catalog CSV column mismatch") as error:
        validate_required_columns(
            str(catalog_path),
            ["source_id", "ra", "dec", "phot_g_mean_mag"],
        )

    message = str(error.value)
    assert "- ra" in message
    assert 'configured "ra", CSV has "RA"' in message


@pytest.mark.unit
def test_build_config_rejects_output_directory_that_is_an_existing_file(
    tmp_path: Path,
    config_text: str,
    write_config: Callable[[str | None], Path],
) -> None:
    """Build output must not silently overwrite a file that occupies the configured directory path."""
    conflict_path = tmp_path / "output"
    conflict_path.write_text("not a directory", encoding="utf-8")
    config_path = write_config(config_text)

    with pytest.raises(ValueError, match="out_dir must be a directory"):
        load_config("build_neighbors_index", str(config_path))


@pytest.mark.unit
def test_build_config_rejects_kdtree_filename_that_escapes_output_directory(
    config_text: str,
    write_config: Callable[[str | None], Path],
) -> None:
    """The KDTree setting is a filename contract, preventing accidental writes outside out_dir."""
    invalid_config = config_text.replace("KDTREE_FILENAME: ckdtree.pkl", "KDTREE_FILENAME: ../tree.pkl")

    with pytest.raises(ValueError, match="must be a filename only"):
        load_config("build_neighbors_index", str(write_config(invalid_config)))


@pytest.mark.unit
def test_target_column_error_lists_available_headers(tmp_path: Path) -> None:
    """Target CSV validation should explain a missing configured source-ID column before reading rows."""
    targets_path = tmp_path / "targets.csv"
    targets_path.write_text("Target_ID\n1001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Targets CSV column mismatch") as error:
        validate_target_column(str(targets_path), "source_id")

    message = str(error.value)
    assert "Target_ID" in message
    assert "source_id" in message


@pytest.mark.unit
def test_query_output_path_rejects_file_named_output(tmp_path: Path) -> None:
    """Query results must fail clearly instead of overwriting a file named output inside an index folder."""
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    (index_dir / "output").write_text("conflict", encoding="utf-8")

    with pytest.raises(ValueError, match="Query results output path must be a directory"):
        create_output_json_path(None, str(index_dir), 47.0, 5.0)


@pytest.mark.unit
def test_query_index_path_rejects_regular_file(tmp_path: Path) -> None:
    """A user selecting a file instead of an index directory receives a direct path-specific error."""
    index_file = tmp_path / "index_file"
    index_file.write_text("not an index directory", encoding="utf-8")

    with pytest.raises(ValueError, match="Query index folder must be a directory"):
        validate_index_directory(str(index_file))
