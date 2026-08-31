# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for terminal progress output that does not require an interactive terminal."""

# A controllable stand-in is injected over the bar's internal event so the animation can
# be stepped deterministically instead of waited on.
# pyright: reportAttributeAccessIssue=false

from __future__ import annotations

from types import SimpleNamespace

import pytest

from photo_cat import pipeline_display


@pytest.mark.unit
def test_color_returns_plain_text_when_colour_is_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-interactive output remains readable and free from terminal escape codes."""
    monkeypatch.setattr(pipeline_display, "USE_COLOR", False)

    assert pipeline_display.color("status", pipeline_display.Style.GREEN) == "status"


@pytest.mark.unit
def test_write_progress_suffix_formats_structured_and_plain_suffixes(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Progress suffixes retain their count and details in both recognized and fallback formats."""
    monkeypatch.setattr(pipeline_display, "USE_COLOR", False)

    pipeline_display.write_progress_suffix("- 2/5 [loading]")
    pipeline_display.write_progress_suffix("plain detail")

    assert capsys.readouterr().out == "  -  2/5 [loading]  plain detail"


@pytest.mark.unit
def test_progress_bar_clamps_progress_and_terminates_completed_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    """Progress rendering handles oversized percentages and emits a newline only for completion."""
    monkeypatch.setattr(pipeline_display, "USE_COLOR", False)
    monkeypatch.setattr(pipeline_display.shutil, "get_terminal_size", lambda fallback: SimpleNamespace(columns=42))

    pipeline_display.progress_bar(125, detail="catalogue", complete=True)

    output = capsys.readouterr().out
    assert "100%" in output
    assert "catalogue" in output
    assert output.endswith("\n")


@pytest.mark.unit
def test_activity_bar_animates_indeterminately_without_fake_percentages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Opaque work advances animation frames without inventing a completion percentage."""
    calls: list[tuple[int, str, bool]] = []

    class ControlledEvent:
        def __init__(self) -> None:
            self.calls = 0

        def is_set(self) -> bool:
            return self.calls >= 4

        def wait(self, interval: float) -> bool:
            self.calls += 1
            return False

    activity_bar = pipeline_display.ActivityBar("loading", interval=0.0)
    activity_bar._done = ControlledEvent()
    monkeypatch.setattr(
        pipeline_display,
        "activity_indicator",
        lambda frame, detail, elapsed, complete=False: calls.append((frame, detail, complete)),
    )

    activity_bar._run()

    assert calls == [
        (0, "loading", False),
        (1, "loading", False),
        (2, "loading", False),
        (3, "loading", False),
    ]


@pytest.mark.unit
def test_indeterminate_indicator_shows_activity_and_elapsed_time_without_percent(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    """Users can see that opaque work is alive while the console avoids misleading percentages."""
    monkeypatch.setattr(pipeline_display, "USE_COLOR", False)
    monkeypatch.setattr(pipeline_display.shutil, "get_terminal_size", lambda fallback: SimpleNamespace(columns=100))

    pipeline_display.activity_indicator(0, "creating environment", 5.2)
    first = capsys.readouterr().out
    pipeline_display.activity_indicator(4, "creating environment", 6.2)
    second = capsys.readouterr().out

    assert "working" in first
    assert "00:05" in first
    assert "creating environment" in first
    assert "%" not in first
    assert first != second
