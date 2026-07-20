# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for honest installer progress reporting."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from photo_cat import install


class RecordingActivity:
    details: list[str] = []

    def __init__(self, detail: str) -> None:
        self.detail = detail

    def __enter__(self):
        self.details.append(self.detail)
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False


@pytest.mark.unit
def test_venv_builder_reports_real_named_phases(monkeypatch: pytest.MonkeyPatch) -> None:
    """The venv builder exposes its actual ordered operations instead of jumping from zero to 100."""
    RecordingActivity.details = []
    monkeypatch.setattr(install, "ActivityBar", RecordingActivity)
    builder = install.ProgressEnvBuilder()

    assert builder._run_phase("creating environment folders", lambda: "context") == "context"
    builder._run_phase("writing pyvenv.cfg", lambda: None)

    assert RecordingActivity.details == [
        "1/6 [creating environment folders]",
        "2/6 [writing pyvenv.cfg]",
    ]
    assert builder.phase_index == 2


@pytest.mark.unit
def test_subprocess_progress_uses_completed_item_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A package command is indeterminate while running and becomes determinate only after real completion."""
    log_path = tmp_path / "install.log"
    log_path.write_text("", encoding="utf-8")
    RecordingActivity.details = []
    determinate_calls: list[tuple[int, str, bool]] = []
    monkeypatch.setattr(install, "INSTALL_LOG_FILE", log_path)
    monkeypatch.setattr(install, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(install, "ActivityBar", RecordingActivity)
    monkeypatch.setattr(install.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    monkeypatch.setattr(
        install,
        "progress_bar",
        lambda percent, detail, complete=False: determinate_calls.append((percent, detail, complete)),
    )

    result = install.run_logged_with_progress(
        ["python", "-m", "pip", "install", "numpy"],
        "Installing numpy",
        "downloading/installing numpy",
        2,
        5,
    )

    assert result is True
    assert RecordingActivity.details == ["downloading/installing numpy"]
    assert determinate_calls == [(40, "2/5 [downloading/installing numpy]", False)]
