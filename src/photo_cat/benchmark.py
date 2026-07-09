# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Benchmark helpers for reproducible PHOTO-CAT performance notes."""

from __future__ import annotations

import platform
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

from . import __version__
from .index_manifest import atomic_write_json


BENCHMARK_SCHEMA_VERSION = 1


def _run_stage(name: str, callback) -> dict[str, Any]:
    start = time.perf_counter()
    tracemalloc.start()
    try:
        status = int(callback() or 0)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    end = time.perf_counter()
    return {
        "stage": name,
        "status": status,
        "duration_seconds": round(end - start, 6),
        "python_tracemalloc_peak_bytes": int(peak),
        "python_tracemalloc_current_bytes": int(current),
    }


def run_benchmark(
    config_path: str | Path | None,
    *,
    run_build: bool = True,
    run_query: bool = True,
) -> dict[str, Any]:
    """Run selected PHOTO-CAT stages and capture timing/reproducibility metadata."""
    if (not run_build and not run_query):
        raise ValueError("Benchmark must run at least one stage.")

    from . import build_neighbors_index, query_contamination_from_index

    resolved_config = None if (config_path is None) else str(Path(config_path).resolve())
    payload: dict[str, Any] = {
        "schema_version": BENCHMARK_SCHEMA_VERSION,
        "photo_cat_version": __version__,
        "config_path": resolved_config,
        "python": sys.version.split()[0],
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "stages": [],
    }

    if run_build:
        payload["stages"].append(
            _run_stage("build-index", lambda: build_neighbors_index.main(config_path))
        )
    if run_query:
        payload["stages"].append(
            _run_stage("query", lambda: query_contamination_from_index.main(config_path))
        )

    payload["total_duration_seconds"] = round(
        sum(float(stage["duration_seconds"]) for stage in payload["stages"]),
        6,
    )
    payload["ok"] = all(int(stage["status"]) == 0 for stage in payload["stages"])
    return payload


def write_benchmark(payload: dict[str, Any], output_path: str | Path) -> str:
    """Write benchmark payload as JSON."""
    atomic_write_json(output_path, payload)
    return str(output_path)
