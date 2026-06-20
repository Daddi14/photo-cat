# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for compact and readable console logging behaviour."""

from __future__ import annotations

import logging

import pytest

from photo_cat import logger_setup


def make_record(level: int, message: str) -> logging.LogRecord:
    """Create a compact log record without coupling tests to global logger handlers."""
    return logging.LogRecord("photo_cat.tests", level, __file__, 1, message, (), None)


@pytest.mark.unit
def test_compact_info_filter_keeps_actionable_messages_and_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Compact mode drops decorative rules but never hides warnings or useful progress messages."""
    monkeypatch.setattr(logger_setup, "COMPACT_LOG", True)
    log_filter = logger_setup._CompactInfoFilter()

    assert not log_filter.filter(make_record(logging.INFO, "=========="))
    assert not log_filter.filter(make_record(logging.INFO, "unrelated verbose message"))
    assert log_filter.filter(make_record(logging.INFO, "Loading catalog: sample.csv"))
    assert log_filter.filter(make_record(logging.WARNING, "A warning remains visible"))


@pytest.mark.unit
def test_compact_info_filter_leaves_regular_logging_untouched_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabling compact mode must preserve all existing application log messages."""
    monkeypatch.setattr(logger_setup, "COMPACT_LOG", False)

    assert logger_setup._CompactInfoFilter().filter(make_record(logging.INFO, "unrelated verbose message"))


@pytest.mark.unit
def test_color_formatter_normalizes_errors_and_applies_level_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Console errors use one prefix and no ANSI sequences when colour is unavailable."""
    monkeypatch.setattr(logger_setup, "USE_COLOR", False)
    formatter = logger_setup._ColorFormatter()

    assert formatter.format(make_record(logging.ERROR, "ERROR: problem details")) == "[ERROR] problem details"
    assert formatter.format(make_record(logging.WARNING, "configuration warning")) == "[WARN]  configuration warning"
    assert formatter.format(make_record(logging.DEBUG, "diagnostic detail")) == "[DEBUG] diagnostic detail"


@pytest.mark.unit
def test_color_formatter_highlights_saved_result_path_when_colours_are_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The result-file path remains visually distinct without changing its human-readable text."""
    monkeypatch.setattr(logger_setup, "USE_COLOR", True)
    formatter = logger_setup._ColorFormatter()

    rendered = formatter.format(make_record(logging.INFO, "Results saved to: output/result.json"))

    assert "Results saved to: " in rendered
    assert f"{logger_setup._ColorFormatter.YELLOW}output/result.json" in rendered
    assert rendered.endswith(logger_setup._ColorFormatter.RESET)


@pytest.mark.unit
def test_get_logger_installs_the_compact_root_handler_once() -> None:
    """The public logger factory configures one reusable root handler for command entry points."""
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    root_logger.handlers.clear()

    try:
        logger = logger_setup.get_logger("photo_cat.tests.logger_setup")

        assert logger.level == logging.INFO
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0].formatter, logger_setup._ColorFormatter)
        assert any(isinstance(log_filter, logger_setup._CompactInfoFilter) for log_filter in root_logger.handlers[0].filters)
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(original_handlers)
        root_logger.setLevel(original_level)
