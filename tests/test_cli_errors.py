# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for CLI failure statuses and actionable user-facing errors."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from photo_cat import cli


@pytest.mark.regression
def test_build_index_cli_returns_one_and_explains_missing_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """A missing explicit config is a normal user error, not a Python traceback from the CLI entry point."""
    monkeypatch.chdir(tmp_path)

    result = cli.main(["build-index", "--config", "missing.yaml"])

    assert result == 1
    assert "ERROR: config.yaml was not found here:" in capsys.readouterr().err


@pytest.mark.regression
def test_build_index_cli_returns_one_and_explains_missing_catalogue(
    write_config: Callable[[str | None], Path],
    capsys,
) -> None:
    """A missing overridden catalogue path must identify input_catalog so scripted callers can repair it."""
    config_path = write_config()

    result = cli.main([
        "build-index",
        "--config",
        str(config_path),
        "--input-catalog",
        "missing_catalog.csv",
    ])

    assert result == 1
    error = capsys.readouterr().err
    assert "ERROR: input_catalog was not found:" in error
    assert "missing_catalog.csv" in error
