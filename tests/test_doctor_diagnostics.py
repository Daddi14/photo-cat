# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for individual doctor diagnostic branches and stable report rendering."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from photo_cat import doctor


@pytest.mark.unit
def test_doctor_reporter_renders_the_legacy_text_statuses(capsys) -> None:
    """Text diagnostics retain the established pass, warning, failure, and information prefixes."""
    reporter = doctor.DoctorReporter("text")
    reporter.status("python", "Python", True, "3.13")
    reporter.warning("project_venv", ".venv", "stale")
    reporter.status("configuration", "config.yaml", False, "missing")
    reporter.info("project_runtime", ".runtime", "not required")

    assert capsys.readouterr().out.splitlines() == [
        "[ OK ] Python: 3.13",
        "[WARN] .venv: stale",
        "[FAIL] config.yaml: missing",
        "[INFO] .runtime: not required",
    ]


@pytest.mark.unit
def test_check_package_version_reports_a_missing_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor marks a missing distribution as a hard failure even outside a source checkout."""
    monkeypatch.setattr(doctor, "installed_package_version", lambda: None)
    reporter = doctor.DoctorReporter("json")

    assert doctor.check_package_version(None, reporter) is False

    assert reporter.payload()["checks"] == [
        {
            "name": "photo_cat_package",
            "status": "fail",
            "message": "PHOTO-CAT package",
            "detail": "not installed in this environment",
        }
    ]


@pytest.mark.unit
def test_check_imports_records_an_individual_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing scientific dependency is individually identifiable in automation diagnostics."""
    original_import = importlib.import_module

    def controlled_import(module_name: str):
        if (module_name == "scipy"):
            raise ImportError("simulated missing scipy")
        return original_import(module_name)

    monkeypatch.setattr(doctor.importlib, "import_module", controlled_import)
    reporter = doctor.DoctorReporter("json")

    assert doctor.check_imports(reporter) is False

    scipy_check = next(check for check in reporter.payload()["checks"] if check["name"] == "dependency_scipy")
    assert scipy_check["status"] == "fail"
    assert "simulated missing scipy" in scipy_check["detail"]


@pytest.mark.unit
def test_check_project_venv_accepts_a_valid_local_layout(tmp_path: Path) -> None:
    """A complete local venv layout is reported as healthy without launching its interpreter."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    venv_dir = project_dir / ".venv"
    python_path = doctor.project_venv_python_path(venv_dir)
    python_path.parent.mkdir(parents=True)
    (venv_dir / "pyvenv.cfg").write_text("home = /python\n", encoding="utf-8")
    python_path.write_text("placeholder", encoding="utf-8")
    (venv_dir / ".photo_cat_project_dir").write_text(str(project_dir), encoding="utf-8")
    reporter = doctor.DoctorReporter("json")

    assert doctor.check_project_virtual_environment(project_dir, reporter) is True

    assert reporter.payload()["checks"][0]["status"] == "pass"


@pytest.mark.unit
def test_check_project_venv_rejects_a_file_at_the_venv_path(tmp_path: Path) -> None:
    """A non-directory .venv path is a hard repair problem rather than a recoverable launcher warning."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".venv").write_text("not a directory", encoding="utf-8")
    reporter = doctor.DoctorReporter("json")

    assert doctor.check_project_virtual_environment(project_dir, reporter) is False

    check = reporter.payload()["checks"][0]
    assert check["status"] == "fail"
    assert "exists but is not a folder" in check["detail"]


@pytest.mark.unit
def test_check_project_venv_warns_when_pyvenv_metadata_is_missing(tmp_path: Path) -> None:
    """A partial but removable venv remains a warning so the launcher can rebuild it automatically."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".venv").mkdir()
    reporter = doctor.DoctorReporter("json")

    assert doctor.check_project_virtual_environment(project_dir, reporter) is True

    check = reporter.payload()["checks"][0]
    assert check["status"] == "warn"
    assert check["detail"] == "missing pyvenv.cfg; run a launcher to rebuild it"


@pytest.mark.unit
def test_check_project_context_reports_source_folder_resources(tmp_path: Path) -> None:
    """Source-project diagnostics enumerate version, config, venv, and runtime context separately."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "VERSION").write_text("1.7.0\n", encoding="utf-8")
    (project_dir / "config.yaml").write_text("execution: {}\n", encoding="utf-8")
    reporter = doctor.DoctorReporter("json")

    assert doctor.check_project_context(project_dir, reporter=reporter) is True

    names = [check["name"] for check in reporter.payload()["checks"]]
    assert names == ["project_folder", "project_version", "configuration", "project_venv", "project_runtime"]


@pytest.mark.unit
def test_normalize_path_text_handles_backslash_separators(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stale-marker comparisons normalise Windows-style separators before comparing locations."""
    monkeypatch.setattr(doctor.os, "name", "nt", raising=False)

    assert doctor.normalize_path_text(r"C:\PHOTO-CAT\.venv") == "c:/photo-cat/.venv"


@pytest.mark.unit
def test_emit_json_report_writes_one_json_document(capsys) -> None:
    """JSON mode emits a compact single document without human-oriented header lines."""
    reporter = doctor.DoctorReporter("json")
    reporter.info("project_folder", "Project folder", "package-install mode")

    doctor.emit_json_report(reporter)

    output = capsys.readouterr().out
    assert output.count("\n") == 1
    assert '"schema_version": 1' in output

@pytest.mark.unit
def test_read_project_version_uses_the_source_version_file_when_available(tmp_path: Path) -> None:
    """Project-mode diagnostics expose the release version recorded by a local checkout."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "VERSION").write_text("1.7.0\n", encoding="utf-8")

    assert doctor.read_project_version(project_dir) == "1.7.0"
