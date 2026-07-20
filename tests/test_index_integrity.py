# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for safe, versioned, and crash-consistent index handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np
import pytest

from photo_cat.build_neighbors_index import (
    exclusive_build_lock,
    main as build_main,
    reconcile_resume_file,
    write_checkpoint,
)
from photo_cat.index_manifest import load_index_manifest, validate_index_structure
from photo_cat.load_config import ContaminationModelConfig, QueryConfig
from photo_cat.path_policy import index_paths
from photo_cat.query_contamination_from_index import (
    load_catalog_arrays,
    main as query_main,
    prepare_query_runtime,
    process_target,
)


@pytest.mark.regression
def test_query_handles_an_index_with_no_neighbor_entries(
    write_minimal_index: Callable[[], Path],
    tmp_path: Path,
) -> None:
    """A valid empty binary index must produce a no-contaminant result instead of a memmap error."""
    index_dir = write_minimal_index()
    config_path = tmp_path / "query.yaml"
    config_path.write_text(
        f"""
query_contamination_from_index:
  io:
    INDEX_DIR: {index_dir.as_posix()}
    TARGETS_INPUT: null
    targets: ["1001"]
    target_source_id_column: source_id
  settings:
    field_of_view_arcsec: 47.0
    delta_mag: 5.0
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert query_main(config_path) == 0

    result_path = next((index_dir / "results").glob("*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result[0]["num_contaminants"] == 0
    assert result[0]["flux_fraction_extra"] == 0.0


@pytest.mark.regression
def test_query_can_preserve_missing_target_rows(
    write_minimal_index: Callable[[], Path],
    tmp_path: Path,
) -> None:
    """Opt-in missing-target rows should keep batch target lists auditable."""
    index_dir = write_minimal_index()
    config_path = tmp_path / "query.yaml"
    config_path.write_text(
        f"""
query_contamination_from_index:
  io:
    INDEX_DIR: {index_dir.as_posix()}
    TARGETS_INPUT: null
    targets: ["1001", "9999", "not-a-number"]
    target_source_id_column: source_id
  settings:
    field_of_view_arcsec: 47.0
    delta_mag: 5.0
    include_missing_targets: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert query_main(config_path) == 0

    result_path = next((index_dir / "results").glob("*.json"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert [row["source_id"] for row in result] == ["1001", "9999", "not-a-number"]
    assert result[0].get("status", "found") == "found"
    assert result[1]["status"] == "missing_from_index"
    assert result[2]["status"] == "invalid_target_id"
    assert result[1]["flux_fraction_selected"] is None


@pytest.mark.unit
def test_query_allows_an_influence_radius_larger_than_the_built_radius(
    write_minimal_index: Callable[[], Path],
) -> None:
    """An influence radius beyond the index build radius is allowed and recomputed per target."""
    index_dir = write_minimal_index()
    config = QueryConfig(
        INDEX_DIR=str(index_dir),
        TARGETS_INPUT=None,
        field_of_view_arcsec=121.0,
        delta_mag=5.0,
        targets=["1001"],
        target_source_id_column="source_id",
    )

    plan = prepare_query_runtime(config)

    # No longer rejected: the query recomputes neighbours out to the influence radius
    # for the requested targets instead of being capped by the build radius.
    assert config.effective_influence_radius_arcsec > plan.manifest.max_radius_arcsec


@pytest.mark.unit
def test_query_refuses_legacy_pickled_special_ids(
    write_minimal_index: Callable[[], Path],
) -> None:
    """Object arrays must trigger a rebuild instruction without invoking pickle deserialization."""
    index_dir = write_minimal_index()
    np.savez_compressed(
        index_dir / "special_ids.npz",
        internal_ids=np.array([3], dtype=np.int64),
        names=np.array(["unsafe"], dtype=object),
    )

    with pytest.raises(ValueError, match="legacy unsafe object format"):
        load_catalog_arrays(index_dir, targets=["1001"])


@pytest.mark.unit
def test_structural_validation_detects_a_truncated_neighbor_binary(
    write_minimal_index: Callable[[], Path],
) -> None:
    """A completed manifest cannot make a binary with the wrong byte count queryable."""
    index_dir = write_minimal_index()
    np.array([1], dtype=np.int64).tofile(index_dir / "neighbors_ids.bin")
    paths = index_paths(index_dir)
    manifest = load_index_manifest(paths.manifest)

    with pytest.raises(ValueError, match="size does not match"):
        validate_index_structure(paths, manifest)


@pytest.mark.unit
def test_resume_reconciliation_discards_bytes_written_after_the_checkpoint(tmp_path: Path) -> None:
    """Recovery must truncate a flushed-but-uncheckpointed suffix before appending more records."""
    temporary_path = tmp_path / "neighbors_ids.tmp"
    final_path = tmp_path / "neighbors_ids.bin"
    np.array([1, 2, 3], dtype=np.int64).tofile(temporary_path)

    reconcile_resume_file(
        str(temporary_path),
        str(final_path),
        expected_size=2 * np.dtype(np.int64).itemsize,
        checkpoint_complete=False,
    )

    assert np.fromfile(temporary_path, dtype=np.int64).tolist() == [1, 2]


@pytest.mark.regression
def test_complete_checkpoint_finishes_outputs_after_a_finalization_crash(
    write_config: Callable[[str | None], Path],
    tmp_path: Path,
) -> None:
    """A 100% checkpoint without a manifest must finalize rather than return an unusable index."""
    config_path = write_config()
    assert build_main(config_path) == 0

    paths = index_paths(tmp_path / "output")
    manifest = load_index_manifest(paths.manifest)
    offsets = np.load(paths.offsets, allow_pickle=False)
    write_checkpoint(
        str(paths.root / "resume_checkpoint.npz"),
        manifest.number_of_sources,
        offsets,
        manifest.total_neighbors,
        manifest.build_signature,
    )
    paths.manifest.unlink()

    assert build_main(config_path) == 0
    assert load_index_manifest(paths.manifest).status == "complete"
    assert not (paths.root / "resume_checkpoint.npz").exists()


@pytest.mark.unit
def test_build_lock_rejects_a_concurrent_writer(tmp_path: Path) -> None:
    """Two builders must never append or finalize files in the same index directory concurrently."""
    with exclusive_build_lock(tmp_path):
        with pytest.raises(RuntimeError, match="Another PHOTO-CAT build"):
            with exclusive_build_lock(tmp_path):
                pytest.fail("A second build unexpectedly acquired the same output lock.")


@pytest.mark.unit
def test_flux_and_contaminant_list_use_the_same_magnitude_selection() -> None:
    """A neighbour excluded by delta_mag must not contribute hidden flux to an empty result list."""
    result = process_target(
        internal_target=1,
        offsets=np.array([0, 1, 1], dtype=np.int64),
        neighbors_mm=np.array([2], dtype=np.int64),
        ra=np.array([10.0, 10.001], dtype=np.float64),
        dec=np.array([20.0, 20.0], dtype=np.float64),
        gmag=np.array([10.0, 20.0], dtype=np.float64),
        real_ids_int=np.array([1001, 1002], dtype=np.int64),
        internal_to_special_name={},
        field_of_view_arcsec=47.0,
        delta_mag=5.0,
    )

    assert result is not None
    assert result["num_contaminants"] == 0
    assert result["flux_fraction_extra"] == 0.0
    assert result["flux_fraction_selected"] == 0.0
    assert result["flux_fraction_all_neighbors"] == pytest.approx(0.01)
    assert result["num_neighbors_in_radius"] == 1
    assert result["num_contaminants_selected"] == 0


@pytest.mark.unit
def test_query_uses_persisted_neighbor_separations_when_available() -> None:
    """A version-2 index that stores separations should avoid recomputing spherical distances."""
    result = process_target(
        internal_target=1,
        offsets=np.array([0, 1, 1], dtype=np.int64),
        neighbors_mm=np.array([2], dtype=np.int64),
        ra=np.array([10.0, 20.0], dtype=np.float64),
        dec=np.array([20.0, 20.0], dtype=np.float64),
        gmag=np.array([10.0, 11.0], dtype=np.float64),
        real_ids_int=np.array([1001, 1002], dtype=np.int64),
        internal_to_special_name={},
        field_of_view_arcsec=47.0,
        delta_mag=5.0,
        neighbor_separations_mm=np.array([1.0], dtype=np.float64),
    )

    assert result is not None
    assert result["num_contaminants"] == 1
    assert result["contaminants"][0]["sep_arcsec"] == 1.0


@pytest.mark.unit
def test_query_reports_weighted_leakage_from_outside_aperture() -> None:
    """A source outside the aperture but inside the influence radius should be explicit in output."""
    result = process_target(
        internal_target=1,
        offsets=np.array([0, 1, 1], dtype=np.int64),
        neighbors_mm=np.array([2], dtype=np.int64),
        ra=np.array([10.0, 20.0], dtype=np.float64),
        dec=np.array([20.0, 20.0], dtype=np.float64),
        gmag=np.array([10.0, 10.0], dtype=np.float64),
        real_ids_int=np.array([1001, 1002], dtype=np.int64),
        internal_to_special_name={},
        field_of_view_arcsec=10.0,
        influence_radius_arcsec=30.0,
        delta_mag=5.0,
        neighbor_separations_mm=np.array([15.0], dtype=np.float64),
        contamination_model=ContaminationModelConfig(
            mode="gaussian_psf", gaussian_fwhm_arcsec=10.0, influence_sigma=7.0
        ),
    )

    assert result is not None
    assert result["num_neighbors_in_radius"] == 0
    assert result["num_neighbors_outside_aperture"] == 1
    assert result["num_contaminants_outside_aperture"] == 1
    assert result["flux_fraction_inside_aperture"] == 0.0
    assert result["flux_fraction_outside_aperture"] > 0.0
    assert result["flux_fraction_total_weighted"] == result["flux_fraction_outside_aperture"]
    assert result["outside_aperture_contaminants"][0]["aperture_location"] == "outside"
