# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Focused unit tests for target-ID resolution and user-facing rejection details."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pytest

from photo_cat.query_contamination_from_index import load_catalog_arrays, resolve_target_internal_ids


@pytest.mark.unit
def test_resolve_target_internal_ids_classifies_numeric_special_invalid_and_missing_values() -> None:
    """Manual target IDs retain valid numeric/special values while distinguishing malformed from absent IDs."""
    targets_internal, invalid, missing = resolve_target_internal_ids(
        ["1001", "HD 216608A", "not-an-id", "9999"],
        {"HD 216608A": 3},
        numeric_real_ids_sorted=np.array([1001, 1002], dtype=np.int64),
        numeric_internal_ids_sorted=np.array([1, 2], dtype=np.int64),
    )

    assert targets_internal == [1, 3]
    assert invalid == ["not-an-id"]
    assert missing == ["9999"]


@pytest.mark.unit
def test_load_catalog_arrays_skips_invalid_and_missing_targets_but_keeps_valid_targets(
    write_minimal_index: Callable[[], Path],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Mixed target lists should process valid IDs and warn about malformed or unavailable values."""
    index_dir = write_minimal_index()

    *_, targets_internal = load_catalog_arrays(
        str(index_dir),
        targets=["1001", "not-an-id", "9999", "HD 216608A"],
    )

    assert targets_internal == [1, 3]
    assert "neither numeric source_id values nor recognised special IDs" in caplog.text
    assert "not found in the built index" in caplog.text


@pytest.mark.unit
def test_load_catalog_arrays_explains_when_all_target_ids_are_invalid_or_missing(
    write_minimal_index: Callable[[], Path],
) -> None:
    """A failed target request should state which IDs were unrecognised versus absent from the current index."""
    index_dir = write_minimal_index()

    with pytest.raises(ValueError, match="None of the configured targets") as error:
        load_catalog_arrays(str(index_dir), targets=["not-an-id", "9999"])

    message = str(error.value)
    assert "Unrecognised target values: not-an-id" in message
    assert "Target values not found in the index: 9999" in message
