# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for actionable configuration-file validation failures."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from photo_cat.load_config import load_config, load_configuration_document


@pytest.mark.regression
def test_invalid_yaml_is_reported_as_a_configuration_error(tmp_path: Path) -> None:
    """Malformed YAML should produce a stable error without exposing parser internals as the contract."""
    config_path = tmp_path / "broken.yaml"
    config_path.write_text("build_neighbors_index: [\n", encoding="utf-8")

    with pytest.raises(ValueError, match="config.yaml contains invalid YAML"):
        load_configuration_document(config_path)


@pytest.mark.unit
def test_build_config_rejects_non_finite_radius(
    config_text: str,
    write_config: Callable[[str | None], Path],
) -> None:
    """A NaN radius would make spatial-index behaviour undefined and must be rejected at parsing time."""
    invalid_config = config_text.replace("max_radius_arcsec: 120.0", "max_radius_arcsec: .nan")

    with pytest.raises(ValueError, match="max_radius_arcsec must be a finite number"):
        load_config("build_neighbors_index", write_config(invalid_config), validate_runtime=False)


@pytest.mark.unit
def test_build_config_rejects_duplicate_catalog_column_names(
    config_text: str,
    write_config: Callable[[str | None], Path],
) -> None:
    """A duplicate logical column mapping would silently overwrite data during catalogue normalization."""
    invalid_config = config_text.replace("dec: dec", "dec: ra")

    with pytest.raises(ValueError, match="columns must be different"):
        load_config("build_neighbors_index", write_config(invalid_config), validate_runtime=False)


@pytest.mark.unit
def test_query_config_rejects_non_list_manual_targets(
    config_text: str,
    write_config: Callable[[str | None], Path],
) -> None:
    """Manual targets remain a typed list so IDs are not split or coerced unpredictably."""
    invalid_config = config_text.replace("targets: []", "targets: 1001")

    with pytest.raises(ValueError, match="io.targets must be a list"):
        load_config("query_contamination_from_index", write_config(invalid_config), validate_runtime=False)
