# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for process-state boundaries around CLI and pipeline runtime execution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from photo_cat import cli, config_and_run, doctor
from photo_cat.load_config import ExecutionConfig


@pytest.mark.unit
def test_scoped_config_environment_restores_absent_and_existing_parent_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy GUI setup may use an environment variable only inside a scope that always restores it."""
    selected = tmp_path / "selected.yaml"

    monkeypatch.delenv("PHOTO_CAT_CONFIG", raising=False)
    with cli.scoped_config_environment(selected):
        assert os.environ["PHOTO_CAT_CONFIG"] == str(selected)
    assert "PHOTO_CAT_CONFIG" not in os.environ

    monkeypatch.setenv("PHOTO_CAT_CONFIG", "parent.yaml")
    with cli.scoped_config_environment(None):
        assert "PHOTO_CAT_CONFIG" not in os.environ
    assert os.environ["PHOTO_CAT_CONFIG"] == "parent.yaml"


@pytest.mark.unit
def test_compact_environment_scopes_runtime_config_to_child_process_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Child execution receives explicit config and source paths without changing parent environment values."""
    selected = tmp_path / "selected.yaml"
    monkeypatch.setenv("PHOTO_CAT_CONFIG", "parent.yaml")
    monkeypatch.setenv("PYTHONPATH", "existing-path")
    monkeypatch.setenv("NO_COLOR", "1")

    environment = config_and_run.compact_environment(selected)

    assert environment["PHOTO_CAT_CONFIG"] == str(selected)
    assert environment["PYTHONPATH"].endswith(os.pathsep + "existing-path")
    assert "NO_COLOR" not in environment
    assert os.environ["PHOTO_CAT_CONFIG"] == "parent.yaml"
    assert os.environ["NO_COLOR"] == "1"


@pytest.mark.unit
def test_run_configured_pipeline_passes_one_explicit_config_to_each_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pipeline orchestration routes one resolved config path to every child stage without global mutation."""
    selected = tmp_path / "selected.yaml"
    calls: list[tuple[str, int, int, Path]] = []

    def fake_run_stage(stage, index, total, config_path):
        calls.append((stage.module_name, index, total, config_path))

    monkeypatch.setattr(config_and_run, "run_stage", fake_run_stage)

    config_and_run.run_configured_pipeline(
        [config_and_run.BUILD_STAGE, config_and_run.QUERY_STAGE],
        selected,
    )

    assert calls == [
        ("build_neighbors_index", 1, 2, selected),
        ("query_contamination_from_index", 2, 2, selected),
    ]


@pytest.mark.unit
def test_pipeline_main_leaves_callers_working_directory_unchanged_when_no_stage_is_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolving pipeline configuration must not change the caller cwd merely to run validation or display output."""
    selected = tmp_path / "selected.yaml"
    original_cwd = Path.cwd()

    monkeypatch.setattr(config_and_run, "resolve_config_path", lambda value=None: selected)
    monkeypatch.setattr(
        config_and_run,
        "load_config",
        lambda section, config_path: ExecutionConfig(False, False, True),
    )
    monkeypatch.setattr(config_and_run, "write_header", lambda title, config_path: None)

    assert config_and_run.main(selected) == 0
    assert Path.cwd() == original_cwd


@pytest.mark.unit
def test_doctor_explicit_config_path_precedes_environment_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doctor checks honour an explicit CLI config choice without requiring callers to overwrite environment state."""
    explicit = tmp_path / "explicit.yaml"
    environment = tmp_path / "environment.yaml"
    monkeypatch.setenv("PHOTO_CAT_CONFIG", str(environment))

    resolved, was_explicit = doctor.resolve_config_path(None, explicit)

    assert resolved == explicit.resolve()
    assert was_explicit is True
