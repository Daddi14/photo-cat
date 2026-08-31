# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Compare PHOTO-CAT contamination estimates with an external reference table."""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Any

import pandas as pd

from .index_manifest import atomic_write_json


VALIDATION_SCHEMA_VERSION = 1


def validate_against_reference(
    result_rows: list[dict[str, Any]],
    reference_csv: str | Path,
    *,
    prediction_metric: str = "flux_fraction_total_weighted",
    source_id_column: str = "source_id",
    reference_column: str = "contamination_percent",
    threshold_percent: float | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Join by source ID and return validation statistics plus matched residual rows."""
    dataframe = pd.read_csv(reference_csv, dtype={source_id_column: "string"})
    missing = {source_id_column, reference_column}.difference(dataframe.columns)
    if (missing):
        raise ValueError(f"Reference CSV is missing required columns: {', '.join(sorted(missing))}")

    reference: dict[str, float] = {}
    for source_id, value in zip(dataframe[source_id_column], dataframe[reference_column]):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if (math.isfinite(numeric)):
            reference[str(source_id)] = numeric

    matched: list[dict[str, Any]] = []
    for row in result_rows:
        source_id = str(row.get("source_id", ""))
        predicted_value: Any = row.get(prediction_metric)
        if (predicted_value is None and prediction_metric == "flux_fraction_total_weighted"):
            predicted_value = row.get("flux_fraction_all_neighbors", row.get("flux_fraction_selected"))
        if (predicted_value is None):
            continue
        try:
            predicted = float(predicted_value)
        except (TypeError, ValueError):
            continue
        if (source_id not in reference or not math.isfinite(predicted)):
            continue
        residual = predicted - reference[source_id]
        matched.append(
            {
                "source_id": source_id,
                "predicted_percent": predicted,
                "reference_percent": reference[source_id],
                "residual_percent": residual,
                "absolute_error_percent": abs(residual),
            }
        )

    residuals = [row["residual_percent"] for row in matched]
    absolute_errors = [row["absolute_error_percent"] for row in matched]
    squared_errors = [value * value for value in residuals]
    statistics_payload: dict[str, Any] = {
        "matched_targets": len(matched),
        "result_targets": len(result_rows),
        "reference_targets": len(reference),
        "bias_percent": statistics.fmean(residuals) if residuals else None,
        "median_residual_percent": statistics.median(residuals) if residuals else None,
        "mae_percent": statistics.fmean(absolute_errors) if absolute_errors else None,
        "rmse_percent": math.sqrt(statistics.fmean(squared_errors)) if squared_errors else None,
    }
    if (threshold_percent is not None):
        if (not math.isfinite(threshold_percent) or threshold_percent < 0.0):
            raise ValueError("threshold_percent must be a finite non-negative number.")
        correct = sum(
            (row["predicted_percent"] > threshold_percent) == (row["reference_percent"] > threshold_percent)
            for row in matched
        )
        statistics_payload["threshold_percent"] = threshold_percent
        statistics_payload["threshold_accuracy"] = (correct / len(matched)) if matched else None

    payload = {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "reference_csv": str(Path(reference_csv).resolve()),
        "prediction_metric": prediction_metric,
        "reference_column": reference_column,
        "statistics": statistics_payload,
    }
    return payload, matched


def write_validation(
    payload: dict[str, Any],
    output_path: str | Path,
    matched: list[dict[str, Any]],
    matched_output: str | Path | None = None,
) -> tuple[str, str | None]:
    """Write machine-readable validation statistics and optional matched residuals."""
    atomic_write_json(output_path, payload)
    if (matched_output is None):
        return str(output_path), None
    destination = Path(matched_output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["source_id", "predicted_percent", "reference_percent", "residual_percent", "absolute_error_percent"]
    with destination.open("x", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(matched)
    return str(output_path), str(destination)
