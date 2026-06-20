# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for stable machine-readable PHOTO-CAT doctor diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from photo_cat import cli, doctor


@pytest.mark.regression
def test_doctor_json_output_has_a_versioned_schema(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Automation callers receive one parseable JSON document with stable top-level fields."""
    monkeypatch.setattr(doctor, "find_project_dir", lambda: None)
    monkeypatch.setattr(doctor, "check_python_version", lambda reporter=None: True)
    monkeypatch.setattr(doctor, "check_tkinter", lambda reporter=None: True)
    monkeypatch.setattr(doctor, "check_package_version", lambda project_dir, reporter=None: True)
    monkeypatch.setattr(doctor, "check_imports", lambda reporter=None: True)
    monkeypatch.setattr(doctor, "check_project_context", lambda project_dir, config_path=None, reporter=None: True)

    assert doctor.main(output_format="json") == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == 1
    assert payload["ok"] is True
    assert set(payload) == {"schema_version", "ok", "checks", "summary"}
    assert payload["summary"] == {"passed": 0, "warnings": 0, "failed": 0, "information": 0}


@pytest.mark.regression
def test_doctor_json_reports_failed_checks_without_invalid_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Expected diagnostic failures remain machine-readable and return the documented failure status."""
    monkeypatch.setattr(doctor, "find_project_dir", lambda: None)

    def failing_python_check(reporter=None) -> bool:
        assert reporter is not None
        reporter.status("python", "Python", False, "unsupported test runtime")
        return False

    monkeypatch.setattr(doctor, "check_python_version", failing_python_check)
    monkeypatch.setattr(doctor, "check_tkinter", lambda reporter=None: True)
    monkeypatch.setattr(doctor, "check_package_version", lambda project_dir, reporter=None: True)
    monkeypatch.setattr(doctor, "check_imports", lambda reporter=None: True)
    monkeypatch.setattr(doctor, "check_project_context", lambda project_dir, config_path=None, reporter=None: True)

    assert doctor.main(output_format="json") == 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["summary"]["failed"] == 1
    assert payload["checks"] == [
        {
            "name": "python",
            "status": "fail",
            "message": "Python",
            "detail": "unsupported test runtime",
        }
    ]


@pytest.mark.unit
def test_doctor_reporter_counts_warning_without_treating_it_as_a_hard_failure() -> None:
    """Recoverable local-environment warnings remain distinct from failed diagnostic checks."""
    reporter = doctor.DoctorReporter("json")
    reporter.status("python", "Python", True, "3.13")
    reporter.warning("project_venv", ".venv", "stale marker; launcher will rebuild")

    payload = reporter.payload()

    assert payload["ok"] is True
    assert payload["summary"] == {"passed": 1, "warnings": 1, "failed": 0, "information": 0}
    assert payload["checks"][1]["status"] == "warn"


@pytest.mark.regression
def test_cli_doctor_format_json_passes_selected_output_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The public CLI forwards the documented --format json selection to the doctor runtime."""
    captured: dict[str, object] = {}

    def fake_main(config_path: Path | None, output_format: str) -> int:
        captured["config_path"] = config_path
        captured["output_format"] = output_format
        return 0

    monkeypatch.setattr(doctor, "main", fake_main)

    assert cli.main(["doctor", "--format", "json"]) == 0
    assert captured["output_format"] == "json"
