# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for local virtual-environment recovery decisions without touching a real project venv."""

from __future__ import annotations

from pathlib import Path

import pytest

from photo_cat import doctor, install


def configure_install_paths(monkeypatch: pytest.MonkeyPatch, project_dir: Path) -> Path:
    """Redirect installer path constants to one temporary project folder for isolated detection tests."""
    venv_dir = project_dir / ".venv"
    monkeypatch.setattr(install, "PROJECT_DIR", project_dir)
    monkeypatch.setattr(install, "VENV_DIR", venv_dir)
    monkeypatch.setattr(install, "VENV_PROJECT_MARKER_FILE", venv_dir / ".photo_cat_project_dir")
    monkeypatch.setattr(install, "LOG_DIR", project_dir / "logs")
    monkeypatch.setattr(install, "INSTALL_LOG_FILE", project_dir / "logs" / "install.log")
    return venv_dir


@pytest.mark.unit
def test_install_detects_a_moved_project_from_its_venv_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A venv marker from another project location must request a safe launcher rebuild."""
    project_dir = tmp_path / "current-project"
    project_dir.mkdir()
    venv_dir = configure_install_paths(monkeypatch, project_dir)
    venv_dir.mkdir()
    (venv_dir / ".photo_cat_project_dir").write_text(str(tmp_path / "old-project"), encoding="utf-8")
    monkeypatch.setattr(install, "venv_python_health_failure", lambda: "")

    reason = install.virtual_environment_rebuild_reason()

    assert "PHOTO-CAT was moved from" in reason
    assert "old-project" in reason


@pytest.mark.unit
def test_install_detects_a_partially_deleted_venv_python(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A present venv missing its Python executable must be rebuilt instead of being reused."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    venv_dir = configure_install_paths(monkeypatch, project_dir)
    venv_dir.mkdir()
    (venv_dir / ".photo_cat_project_dir").write_text(str(project_dir), encoding="utf-8")

    reason = install.virtual_environment_rebuild_reason()

    assert reason == "the virtual environment Python executable is missing"


@pytest.mark.unit
def test_install_detects_an_embedded_old_venv_path_without_a_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy venv metadata pointing to another path must trigger the same safe rebuild path."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    venv_dir = configure_install_paths(monkeypatch, project_dir)
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text(f"home = {tmp_path / 'old-project' / '.venv'}\n", encoding="utf-8")
    monkeypatch.setattr(install, "venv_python_health_failure", lambda: "")

    reason = install.virtual_environment_rebuild_reason()

    assert "existing virtual environment still points to" in reason
    assert "old-project" in reason


@pytest.mark.regression
def test_doctor_reports_a_recoverable_stale_venv_warning(tmp_path: Path, capsys) -> None:
    """Doctor must explain stale local environment recovery without treating it as a package-install failure."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    venv_dir = project_dir / ".venv"
    venv_dir.mkdir()
    (venv_dir / ".photo_cat_project_dir").write_text(str(tmp_path / "old-project"), encoding="utf-8")

    assert doctor.check_project_virtual_environment(project_dir) is True

    output = capsys.readouterr().out
    assert "[WARN] .venv: stale project marker points to" in output
    assert "run a launcher to rebuild it" in output


@pytest.mark.unit
def test_doctor_reports_a_missing_venv_python_as_recoverable_warning(tmp_path: Path) -> None:
    """JSON diagnostics must classify a partial venv as recoverable so launchers can repair it."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    venv_dir = project_dir / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /python\n", encoding="utf-8")
    reporter = doctor.DoctorReporter("json")

    assert doctor.check_project_virtual_environment(project_dir, reporter) is True

    payload = reporter.payload()
    assert payload["checks"] == [
        {
            "name": "project_venv",
            "status": "warn",
            "message": ".venv",
            "detail": f"missing Python executable at {doctor.project_venv_python_path(venv_dir)}; run a launcher to rebuild it",
        }
    ]
