# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for stage planning independent of subprocess execution."""

from __future__ import annotations

import pytest

from photo_cat.config_and_run import BUILD_STAGE, QUERY_STAGE, resolve_pipeline_stages, run_pipeline_stages
from photo_cat.load_config import ExecutionConfig


@pytest.mark.unit
def test_resolve_pipeline_stages_preserves_build_then_query_order() -> None:
    """The public pipeline contract always runs index construction before contamination queries."""
    stages = resolve_pipeline_stages(ExecutionConfig(True, True, True))

    assert stages == [BUILD_STAGE, QUERY_STAGE]


@pytest.mark.unit
def test_run_pipeline_stages_supports_a_test_runner_without_subprocesses() -> None:
    """Orchestration can be tested without invoking expensive build/query modules."""
    calls: list[tuple[str, int, int]] = []

    run_pipeline_stages(
        [BUILD_STAGE, QUERY_STAGE],
        lambda stage, index, total: calls.append((stage.module_name, index, total)),
    )

    assert calls == [
        ("build_neighbors_index", 1, 2),
        ("query_contamination_from_index", 2, 2),
    ]
