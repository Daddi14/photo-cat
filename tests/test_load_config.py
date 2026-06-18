# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for configuration parsing, path resolution and validation boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from photo_cat.load_config import BuildConfig, ExecutionConfig, QueryConfig, load_config, resolve_config_path


@pytest.mark.unit
def test_resolve_config_path_prefers_runtime_environment(write_config: Callable[[], Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """A runtime config path must override the repository default without changing the checkout."""
    config_path = write_config()
    monkeypatch.setenv("PHOTO_CAT_CONFIG", str(config_path))

    assert resolve_config_path() == config_path.resolve()


@pytest.mark.unit
def test_load_build_config_resolves_paths(write_config: Callable[[], Path], tmp_path: Path) -> None:
    """Build config converts relative user paths to paths anchored at config.yaml."""
    config = load_config("build_neighbors_index", str(write_config()))

    assert isinstance(config, BuildConfig)
    assert config.input_catalog == str((tmp_path / "catalog.csv").resolve())
    assert config.out_dir == str((tmp_path / "output").resolve())
    assert config.use_dask is False
    assert config.usecolumns == ["source_id", "ra", "dec", "phot_g_mean_mag"]


@pytest.mark.unit
def test_load_query_and_execution_configs(write_config: Callable[[], Path], tmp_path: Path) -> None:
    """Query and execution sections remain separate public configuration contracts."""
    config_path = write_config()
    query = load_config("query_contamination_from_index", str(config_path))
    execution = load_config("execution", str(config_path))

    assert isinstance(query, QueryConfig)
    assert query.INDEX_DIR == str((tmp_path / "output").resolve())
    assert query.TARGETS_INPUT == str((tmp_path / "targets.csv").resolve())
    assert query.field_of_view_arcsec == 47.0
    assert query.delta_mag == 5.0

    assert isinstance(execution, ExecutionConfig)
    assert execution.run_build is True
    assert execution.run_query is True


@pytest.mark.unit
def test_load_config_rejects_unknown_section(write_config: Callable[[], Path]) -> None:
    """Unknown config sections should fail before a pipeline stage starts."""
    with pytest.raises(ValueError, match="Unknown configuration section"):
        load_config("not_a_real_section", str(write_config()))


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("use_dask: definitely", "use_dask must be true or false"),
        ("max_radius_arcsec: 0", "max_radius_arcsec must be greater than 0.0"),
        ("chunk_size: 0", "chunk_size must be a positive integer"),
        ("field_of_view_arcsec: 0", "field_of_view_arcsec must be greater than 0.0"),
    ],
)
@pytest.mark.unit
def test_load_config_rejects_invalid_setting_types_and_ranges(
    write_config: Callable[[str | None], Path],
    config_text: str,
    replacement: str,
    message: str,
) -> None:
    """Malformed numeric and boolean settings fail at config parsing, not during expensive analysis."""
    if (replacement.startswith("field_of_view_arcsec")):
        modified = config_text.replace("field_of_view_arcsec: 47.0", replacement)
        section = "query_contamination_from_index"
    elif (replacement.startswith("use_dask")):
        modified = config_text.replace("use_dask: false", replacement)
        section = "build_neighbors_index"
    elif (replacement.startswith("max_radius_arcsec")):
        modified = config_text.replace("max_radius_arcsec: 120.0", replacement)
        section = "build_neighbors_index"
    else:
        modified = config_text.replace("chunk_size: 2", replacement)
        section = "build_neighbors_index"

    with pytest.raises(ValueError, match=message):
        load_config(section, str(write_config(modified)))
