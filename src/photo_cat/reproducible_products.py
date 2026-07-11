# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Helpers for reproducible paper/product generation."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .config_and_run import main as run_pipeline
from .index_manifest import atomic_write_json, sha256_file
from .load_config import QUERY_SECTION, QueryConfig, load_config
from .result_products import (
    load_result_rows,
    write_matplotlib_plot,
    write_plot,
    write_report,
    write_summary,
    summarize_results,
)


def latest_result_json(index_dir: str | Path) -> Path:
    """Return the newest query result JSON under an index output directory."""
    output_dir = Path(index_dir) / "output"
    candidates = sorted(
        (path for path in output_dir.glob("*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if (not candidates):
        raise ValueError(f"No query result JSON files were found in {output_dir}.")
    return candidates[0]


def configured_result_json(config_path: str | Path) -> Path:
    """Find the newest result produced by a config's query index directory."""
    query_config = load_config(QUERY_SECTION, config_path, validate_runtime=False)
    if (not isinstance(query_config, QueryConfig)):
        raise RuntimeError("Failed to load query configuration.")
    return latest_result_json(query_config.INDEX_DIR)


def materialize_result_products(
    result_json: str | Path,
    out_dir: str | Path,
    *,
    matplotlib: bool = False,
) -> dict[str, Any]:
    """Write summary, plots, and report for one result JSON."""
    result_path = Path(result_json)
    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    copied_result = destination / result_path.name
    if (result_path.resolve() != copied_result.resolve()):
        shutil.copy2(result_path, copied_result)

    rows = load_result_rows(result_path)
    summary = summarize_results(rows, source_path=result_path)
    summary_path = destination / f"{result_path.stem}_summary.json"
    write_summary(summary, summary_path, "json")

    plot_backend = "matplotlib" if matplotlib else "svg"
    plot_suffix = "png" if matplotlib else "svg"
    plot_paths: dict[str, str] = {}
    for kind in ("contaminant-counts", "flux", "separations-normalized", "flux-vs-separation", "sky-map"):
        plot_path = destination / f"{result_path.stem}_{kind}.{plot_suffix}"
        if matplotlib:
            write_matplotlib_plot(rows, kind, plot_path)
        else:
            write_plot(rows, kind, plot_path)
        plot_paths[kind] = str(plot_path)

    report_path = destination / f"{result_path.stem}_report.html"
    write_report(rows, result_path, report_path, "html")

    return {
        "source_result_json": str(result_path.resolve()),
        "copied_result_json": str(copied_result),
        "result_sha256": sha256_file(result_path),
        "summary_json": str(summary_path),
        "plots": plot_paths,
        "plot_backend": plot_backend,
        "report_html": str(report_path),
    }


def reproduce_paper_products(
    configs: list[str | Path],
    result_jsons: list[str | Path],
    out_dir: str | Path,
    *,
    run_configs: bool = False,
    matplotlib: bool = False,
) -> dict[str, Any]:
    """Generate a reproducibility manifest and derived products for paper results."""
    if (not configs and not result_jsons):
        raise ValueError("Provide at least one --config or --result-json.")

    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)

    config_records: list[dict[str, Any]] = []
    resolved_results = [Path(path) for path in result_jsons]
    for config in configs:
        config_path = Path(config)
        if run_configs:
            status = run_pipeline(config_path)
            if (status != 0):
                raise RuntimeError(f"Pipeline failed for config: {config_path}")
        result_path = configured_result_json(config_path)
        resolved_results.append(result_path)
        copied_config = destination / config_path.name
        if (config_path.resolve() != copied_config.resolve()):
            shutil.copy2(config_path, copied_config)
        config_records.append(
            {
                "config": str(config_path.resolve()),
                "config_copy": str(copied_config),
                "config_sha256": sha256_file(config_path),
                "latest_result_json": str(result_path.resolve()),
            }
        )

    product_records = [
        materialize_result_products(result_path, destination / Path(result_path).stem, matplotlib=matplotlib)
        for result_path in resolved_results
    ]
    payload = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "photo_cat_version": __version__,
        "configs": config_records,
        "products": product_records,
    }
    manifest_path = destination / "paper_reproduction_manifest.json"
    atomic_write_json(manifest_path, payload)
    payload["manifest_path"] = str(manifest_path)
    return payload
