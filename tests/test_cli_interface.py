# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for the public top-level command interface."""

from __future__ import annotations

import pytest

from photo_cat import __version__, cli


@pytest.mark.regression
def test_cli_version_matches_the_package_release_metadata(capsys) -> None:
    """Automation can discover the release version without needing a configuration file."""
    assert cli.main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == __version__


@pytest.mark.regression
def test_cli_without_a_command_prints_top_level_help(capsys) -> None:
    """Invoking the command alone remains a successful discoverability path for new users."""
    assert cli.main([]) == 0

    output = capsys.readouterr().out
    assert "usage: photo-cat" in output
    assert "build-index" in output
    assert "doctor" in output
