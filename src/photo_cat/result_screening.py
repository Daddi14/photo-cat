# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Turn contamination metrics into explicit, reproducible target-screening decisions."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from .index_manifest import atomic_write_json


SCREENING_SCHEMA_VERSION = 1
DEFAULT_METRIC = "flux_fraction_total_weighted"


def _metric_value(row: dict[str, Any], metric: str) -> float | None:
    """Read a finite metric while providing compatibility fallbacks."""
    value: Any = row.get(metric)
    if (value is None and metric == DEFAULT_METRIC):
        value = row.get("flux_fraction_all_neighbors", row.get("flux_fraction_selected"))
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def screen_results(
    rows: list[dict[str, Any]],
    *,
    metric: str = DEFAULT_METRIC,
    accept_max_percent: float = 5.0,
    review_max_percent: float = 20.0,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Rank targets and assign accept/review/reject decisions from explicit thresholds."""
    if (not math.isfinite(accept_max_percent) or not math.isfinite(review_max_percent)):
        raise ValueError("Screening thresholds must be finite numbers.")
    if (accept_max_percent < 0.0 or review_max_percent < accept_max_percent):
        raise ValueError("Require 0 <= accept_max_percent <= review_max_percent.")

    decisions: list[dict[str, Any]] = []
    for row in rows:
        source_id = str(row.get("source_id", ""))
        value = _metric_value(row, metric)
        if (value is None):
            decision = "unresolved"
            reasons = [f"{metric} is unavailable"]
        elif (value <= accept_max_percent):
            decision = "accept"
            reasons = [f"{metric} <= {accept_max_percent:g}%"]
        elif (value <= review_max_percent):
            decision = "review"
            reasons = [f"{accept_max_percent:g}% < {metric} <= {review_max_percent:g}%"]
        else:
            decision = "reject"
            reasons = [f"{metric} > {review_max_percent:g}%"]

        outside_flux = _metric_value(row, "flux_fraction_outside_aperture")
        if (outside_flux is not None and outside_flux > 0.0):
            reasons.append(f"outside-aperture weighted flux = {outside_flux:g}%")

        decisions.append(
            {
                "source_id": source_id,
                "decision": decision,
                "risk_metric": metric,
                "risk_score_percent": value,
                "decision_reasons": reasons,
            }
        )

    decisions.sort(
        key=lambda item: (
            item["risk_score_percent"] is None,
            -(item["risk_score_percent"] or 0.0),
            item["source_id"],
        )
    )
    counts = Counter(item["decision"] for item in decisions)
    return {
        "schema_version": SCREENING_SCHEMA_VERSION,
        "source_result_json": None if source_path is None else str(Path(source_path).resolve()),
        "metric": metric,
        "thresholds_percent": {
            "accept_max": accept_max_percent,
            "review_max": review_max_percent,
        },
        "summary": {name: counts.get(name, 0) for name in ("accept", "review", "reject", "unresolved")},
        "decisions": decisions,
    }


def write_screening(payload: dict[str, Any], output_path: str | Path, output_format: str) -> str:
    """Write a screening result as JSON, CSV, or Markdown."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if (output_format == "json"):
        atomic_write_json(destination, payload)
        return str(destination)
    if (output_format == "csv"):
        with destination.open("x", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["rank", "source_id", "decision", "risk_metric", "risk_score_percent", "decision_reasons"],
            )
            writer.writeheader()
            for rank, item in enumerate(payload["decisions"], start=1):
                writer.writerow({**item, "rank": rank, "decision_reasons": json.dumps(item["decision_reasons"])})
        return str(destination)
    if (output_format != "markdown"):
        raise ValueError("Screening format must be one of: json, csv, markdown.")

    lines = [
        "# PHOTO-CAT target screening",
        "",
        f"Metric: `{payload['metric']}`",
        "",
        "| Rank | Source ID | Decision | Risk (%) | Reasons |",
        "|---:|---|---|---:|---|",
    ]
    for rank, item in enumerate(payload["decisions"], start=1):
        score = "" if item["risk_score_percent"] is None else f"{item['risk_score_percent']:.6g}"
        reasons = "; ".join(item["decision_reasons"]).replace("|", "\\|")
        lines.append(f"| {rank} | {item['source_id']} | {item['decision']} | {score} | {reasons} |")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(destination)
