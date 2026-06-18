# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for isolated configuration parsing and explicitly scoped runtime setup."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from photo_cat import config_and_run
from photo_cat.cli_overrides import RuntimeConfigOverride, apply_overrides, load_base_config
from photo_cat.load_config import (
    BUILD_SECTION,
    BuildConfig,
    QueryConfig,
    load_config,
    load_config_from_document,
    load_configuration_document,
    load_pipeline_configuration,
)
from photo_cat.query_contamination_from_index import prepare_query_runtime


@pytest.mark.unit
def test_config_parsing_and_runtime_validation_do_not_create_output_directories(
    write_config: Callable[[], Path],
    tmp_path: Path,
) -> None:
    """Parsing and validation must not create an output folder before build runtime begins."""
    config_path = write_config()
    output_dir = tmp_path / "output"

    parsed = load_config(BUILD_SECTION, config_path, validate_runtime=False)
    validated = load_config(BUILD_SECTION, config_path)

    assert isinstance(parsed, BuildConfig)
    assert isinstance(validated, BuildConfig)
    assert parsed.out_dir == str(output_dir.resolve())
    assert validated.out_dir == str(output_dir.resolve())
    assert not output_dir.exists()


@pytest.mark.unit
def test_configuration_document_returns_isolated_section_copies(write_config: Callable[[], Path]) -> None:
    """One caller cannot mutate YAML section data that a later load must parse independently."""
    document = load_configuration_document(write_config())
    first_section = document.section(BUILD_SECTION)
    first_section["settings"]["chunk_size"] = 999

    parsed = load_config_from_document(BUILD_SECTION, document, validate_runtime=False)

    assert isinstance(parsed, BuildConfig)
    assert parsed.chunk_size == 2


@pytest.mark.unit
def test_pipeline_configuration_uses_one_document_without_cross_section_state_leakage(
    write_config: Callable[[], Path],
) -> None:
    """Build, query, and execution sections stay independently typed when loaded from one YAML document."""
    configuration = load_pipeline_configuration(write_config(), validate_runtime=False)

    assert configuration.build.chunk_size == 2
    assert configuration.query.field_of_view_arcsec == 47.0
    assert configuration.execution.run_build is True
    assert configuration.document.path.name == "config.yaml"


@pytest.mark.unit
def test_apply_overrides_derives_values_without_mutating_the_loaded_base_config(
    write_config: Callable[[], Path],
) -> None:
    """CLI overrides must not alter the original YAML mapping reused by a later command."""
    base_config, _ = load_base_config(write_config())

    derived_config = apply_overrides(
        base_config,
        {
            "chunk_size": 25,
            "catalog_source_id_column": "catalog_id",
        },
    )

    assert base_config["build_neighbors_index"]["settings"]["chunk_size"] == 2
    assert base_config["build_neighbors_index"]["io"]["columns"]["source_id"] == "source_id"
    assert derived_config["build_neighbors_index"]["settings"]["chunk_size"] == 25
    assert derived_config["build_neighbors_index"]["io"]["columns"]["source_id"] == "catalog_id"


@pytest.mark.unit
def test_runtime_override_keeps_parent_config_environment_unchanged(
    write_config: Callable[[], Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Derived CLI YAML files are temporary transport artifacts, not process-global configuration state."""
    config_path = write_config()
    monkeypatch.setenv("PHOTO_CAT_CONFIG", "parent-config.yaml")

    with RuntimeConfigOverride(config_path, {"chunk_size": 25}) as runtime_config_path:
        assert runtime_config_path is not None
        assert runtime_config_path.is_file()
        assert os.environ["PHOTO_CAT_CONFIG"] == "parent-config.yaml"

    assert os.environ["PHOTO_CAT_CONFIG"] == "parent-config.yaml"
    assert runtime_config_path is not None
    assert not runtime_config_path.exists()


@pytest.mark.unit
def test_sequential_runtime_overrides_do_not_leak_values_between_commands(write_config: Callable[[], Path]) -> None:
    """Two override scopes must derive fresh config files rather than reusing earlier command values."""
    config_path = write_config()

    with RuntimeConfigOverride(config_path, {"chunk_size": 10}) as first_path:
        first_config = load_config(BUILD_SECTION, first_path, validate_runtime=False)

    with RuntimeConfigOverride(config_path, {"chunk_size": 20}) as second_path:
        second_config = load_config(BUILD_SECTION, second_path, validate_runtime=False)

    assert isinstance(first_config, BuildConfig)
    assert isinstance(second_config, BuildConfig)
    assert first_config.chunk_size == 10
    assert second_config.chunk_size == 20


@pytest.mark.unit
def test_child_stage_environment_receives_explicit_config_without_mutating_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline subprocesses receive the selected config through a copied environment only."""
    config_path = tmp_path / "selected-config.yaml"
    original_cwd = Path.cwd()
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("PHOTO_CAT_CONFIG", "parent-config.yaml")
    monkeypatch.setattr(config_and_run.subprocess, "run", fake_run)

    config_and_run.run_stage(config_and_run.BUILD_STAGE, 1, 1, config_path)

    environment = captured["kwargs"]["env"]
    assert environment["PHOTO_CAT_CONFIG"] == str(config_path)
    assert os.environ["PHOTO_CAT_CONFIG"] == "parent-config.yaml"
    assert Path.cwd() == original_cwd


@pytest.mark.unit
def test_query_runtime_validation_fails_before_creating_an_output_directory(tmp_path: Path) -> None:
    """A missing index must fail before the query stage creates any result-directory artifact."""
    index_dir = tmp_path / "missing-index"
    query_config = QueryConfig(
        INDEX_DIR=str(index_dir),
        TARGETS_INPUT=None,
        field_of_view_arcsec=47.0,
        delta_mag=5.0,
        targets=["1001"],
        target_source_id_column="source_id",
    )

    with pytest.raises(FileNotFoundError, match="Query index folder was not found"):
        prepare_query_runtime(query_config)

    assert not (index_dir / "output").exists()
