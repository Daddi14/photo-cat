# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for animated progress shown by GUI-launched tools."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from photo_cat import configure_gui
from photo_cat.configure_gui import ConfigGui, tool_progress_text
from photo_cat.i18n import set_language


@pytest.fixture(autouse=True)
def restore_language():
    """Prevent process-wide localization state from leaking to other tests."""
    set_language("en")
    yield
    set_language("en")


@pytest.mark.unit
def test_tool_progress_text_moves_without_inventing_a_percentage() -> None:
    """Silent commands show motion, elapsed time, and identity without fake completion values."""
    first = tool_progress_text(0, "photo-cat publication-plots", 1.0)
    second = tool_progress_text(5, "photo-cat publication-plots", 2.0)

    assert first != second
    assert "working" in first
    assert "00:01" in first
    assert "publication-plots" in first
    assert "%" not in first


@pytest.mark.unit
def test_tool_progress_text_has_localized_terminal_states() -> None:
    """Completed and failed rows remain visible and follow the selected interface language."""
    set_language("it")

    completed = tool_progress_text(4, "photo-cat report", 65.0, "completed")
    failed = tool_progress_text(4, "photo-cat report", 65.0, "failed")

    assert "completato" in completed
    assert "non riuscito" in failed
    assert "01:05" in completed


@pytest.mark.unit
def test_every_run_cli_command_starts_and_finishes_progress(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared GUI command runner wraps every tool, including silent ones, in progress state."""
    events: list[tuple] = []

    class ImmediateThread:
        def __init__(self, target, daemon: bool) -> None:
            self.target = target

        def start(self) -> None:
            self.target()

    class FakeGui:
        def cli_command(self, argv):
            return argv

        def pipeline_environment(self):
            return {}

        def append_output(self, value):
            events.append(("output", value))

        def queue_output(self, value):
            # The runner buffers output rather than scheduling a callback per line;
            # the double records it directly, since batching is tested separately.
            events.append(("output", value))

        def start_tool_progress(self, label):
            events.append(("start", label))
            return 9

        def finish_tool_progress(self, progress_id, succeeded):
            events.append(("finish", progress_id, succeeded))

        def after(self, delay, callback, *args):
            callback(*args)

    process = SimpleNamespace(stdout=iter([]), returncode=0, wait=lambda: None)
    monkeypatch.setattr(configure_gui.threading, "Thread", ImmediateThread)
    monkeypatch.setattr(configure_gui.subprocess, "Popen", lambda *args, **kwargs: process)

    ConfigGui.run_cli(FakeGui(), ["publication-plots", "result.json"])

    assert ("start", "photo-cat publication-plots") in events
    assert ("finish", 9, True) in events
