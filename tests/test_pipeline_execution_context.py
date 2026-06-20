# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for pipeline execution context and no-op stage selections."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from photo_cat import config_and_run
from photo_cat.load_config import ExecutionConfig


@pytest.mark.unit
def test_compact_environment_scopes_config_and_preserves_parent_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Child-stage environment setup must not mutate terminal or import settings in the parent process."""
    config_path = Path("/tmp/photo-cat-config.yaml")
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("PYTHONPATH", "existing-path")
    monkeypatch.delenv("PHOTO_CAT_COMPACT_LOG", raising=False)

    environment = config_and_run.compact_environment(config_path)

    assert "NO_COLOR" not in environment
    assert environment["PHOTO_CAT_COMPACT_LOG"] == "1"
    assert environment["PHOTO_CAT_CONFIG"] == str(config_path)
    assert environment["PYTHONPATH"] == str(config_and_run.SRC_DIR) + os.pathsep + "existing-path"
    assert os.environ["NO_COLOR"] == "1"
    assert "PHOTO_CAT_COMPACT_LOG" not in os.environ


@pytest.mark.regression
def test_main_reports_success_without_running_stages_when_execution_disables_everything(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A deliberately disabled pipeline is a successful no-op rather than an accidental subprocess invocation."""
    config_path = tmp_path / "config.yaml"
    events: list[object] = []

    monkeypatch.setattr(config_and_run, "enable_windows_ansi", lambda: events.append("ansi"))
    monkeypatch.setattr(config_and_run, "resolve_config_path", lambda path: config_path)
    monkeypatch.setattr(config_and_run, "load_config", lambda section, path: ExecutionConfig(False, False, True))
    monkeypatch.setattr(config_and_run, "write_header", lambda title, path: events.append((title, path)))
    monkeypatch.setattr(config_and_run, "run_configured_pipeline", lambda stages, path: pytest.fail("pipeline must not run"))

    assert config_and_run.main(config_path) == 0
    assert events == ["ansi", ("PHOTO-CAT - Pipeline", config_path)]


@pytest.mark.regression
def test_main_runs_resolved_stages_with_the_selected_configuration_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pipeline execution receives the exact resolved configuration path chosen by the caller."""
    config_path = tmp_path / "config.yaml"
    captured: dict[str, object] = {}

    monkeypatch.setattr(config_and_run, "enable_windows_ansi", lambda: None)
    monkeypatch.setattr(config_and_run, "resolve_config_path", lambda path: config_path)
    monkeypatch.setattr(config_and_run, "load_config", lambda section, path: ExecutionConfig(True, False, True))
    monkeypatch.setattr(config_and_run, "write_header", lambda title, path: captured.update(header=(title, path)))
    monkeypatch.setattr(
        config_and_run,
        "run_configured_pipeline",
        lambda stages, path: captured.update(stages=stages, config_path=path),
    )
    monkeypatch.setattr(config_and_run, "write_success_summary", lambda: captured.update(summary=True))

    assert config_and_run.main(config_path) == 0
    assert captured["stages"] == [config_and_run.BUILD_STAGE]
    assert captured["config_path"] == config_path
    assert captured["summary"] is True
