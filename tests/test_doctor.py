# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for PHOTO-CAT doctor diagnostics."""

from __future__ import annotations

import pytest

import importlib.metadata
from pathlib import Path

from photo_cat import doctor


@pytest.mark.regression
def test_check_package_version_allows_package_install_mode(monkeypatch, capsys) -> None:
    """Installed package diagnostics must not require a source checkout VERSION file."""
    monkeypatch.setattr(doctor, "installed_package_version", lambda: "1.0.1")

    assert doctor.check_package_version(None) is True

    output = capsys.readouterr().out
    assert "[ OK ] PHOTO-CAT package: installed 1.0.1" in output
    assert "expected unknown" not in output


@pytest.mark.regression
def test_check_project_context_skips_project_files_in_package_mode(monkeypatch, capsys) -> None:
    """Package installs should report unavailable checkout files as informational, not failures."""
    monkeypatch.delenv("PHOTO_CAT_CONFIG", raising=False)

    assert doctor.check_project_context(None) is True

    output = capsys.readouterr().out
    assert "[INFO] Project folder: not checked in package-install mode" in output
    assert "[INFO] config.yaml: not checked" in output
    assert "[FAIL]" not in output


@pytest.mark.regression
def test_check_project_context_validates_explicit_config_in_package_mode(tmp_path: Path, monkeypatch, capsys) -> None:
    """An explicit user config remains verifiable even outside a source checkout."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("execution:\n  run_build: false\n  run_query: false\n", encoding="utf-8")
    monkeypatch.setenv("PHOTO_CAT_CONFIG", str(config_path))

    assert doctor.check_project_context(None) is True

    output = capsys.readouterr().out
    assert f"[ OK ] config.yaml: {config_path.resolve()}" in output


@pytest.mark.regression
def test_main_package_mode_returns_success(monkeypatch) -> None:
    """The complete doctor command must succeed for normal PyPI package installs."""
    monkeypatch.delenv("PHOTO_CAT_CONFIG", raising=False)
    monkeypatch.setattr(doctor, "find_project_dir", lambda: None)
    monkeypatch.setattr(doctor, "check_python_version", lambda: True)
    monkeypatch.setattr(doctor, "check_tkinter", lambda: True)
    monkeypatch.setattr(doctor, "check_imports", lambda: True)
    monkeypatch.setattr(doctor, "installed_package_version", lambda: "1.0.1")

    assert doctor.main() == 0
