# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Benchmark helpers for reproducible PHOTO-CAT performance notes."""

from __future__ import annotations

import csv
import json
import os
import platform
import sys
import threading
import time
import tracemalloc
from pathlib import Path
from typing import Any

from . import __version__
from .index_manifest import atomic_write_json


BENCHMARK_SCHEMA_VERSION = 1


class _RssSampler:
    """Optional psutil-backed RSS sampler for native memory visibility."""

    def __init__(self, interval_seconds: float = 0.02):
        self.interval_seconds = interval_seconds
        self.available = False
        self.start_rss: int | None = None
        self.end_rss: int | None = None
        self.peak_rss: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        try:
            import psutil
        except ImportError:
            self._process = None
        else:
            self._process = psutil.Process()
            self.available = True

    def _rss(self) -> int:
        if (self._process is None):
            return 0
        return int(self._process.memory_info().rss)

    def start(self) -> None:
        if (not self.available):
            return
        self.start_rss = self._rss()
        self.peak_rss = self.start_rss
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while (not self._stop.wait(self.interval_seconds)):
            self.peak_rss = max(int(self.peak_rss or 0), self._rss())

    def stop(self) -> None:
        if (not self.available):
            return
        self.end_rss = self._rss()
        self.peak_rss = max(int(self.peak_rss or 0), self.end_rss)
        self._stop.set()
        if (self._thread is not None):
            self._thread.join(timeout=1.0)

    def payload(self) -> dict[str, int | bool | None]:
        return {
            "native_rss_available": self.available,
            "rss_start_bytes": self.start_rss,
            "rss_end_bytes": self.end_rss,
            "rss_peak_bytes": self.peak_rss,
        }


def _run_stage(name: str, callback) -> dict[str, Any]:
    start = time.perf_counter()
    rss = _RssSampler()
    rss.start()
    tracemalloc.start()
    try:
        status = int(callback() or 0)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        rss.stop()
    end = time.perf_counter()
    return {
        "stage": name,
        "status": status,
        "duration_seconds": round(end - start, 6),
        "python_tracemalloc_peak_bytes": int(peak),
        "python_tracemalloc_current_bytes": int(current),
        **rss.payload(),
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
            "logical_cpu_count": os.cpu_count(),
        },
        "stages": [],
    }

    try:
        from .load_config import load_pipeline_configuration

        configuration = load_pipeline_configuration(config_path, validate_runtime=False)
        catalogue_path = Path(configuration.build.input_catalog)
        payload["workload"] = {
            "catalogue_path": str(catalogue_path),
            "catalogue_size_bytes": catalogue_path.stat().st_size if catalogue_path.is_file() else None,
            "max_build_radius_arcsec": configuration.build.max_radius_arcsec,
            "aperture_radius_arcsec": configuration.query.aperture_radius_arcsec,
            "influence_radius_arcsec": configuration.query.effective_influence_radius_arcsec,
            "configured_target_count": len(configuration.query.targets),
        }
    except (FileNotFoundError, OSError, ValueError):
        payload["workload"] = None

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


def benchmark_table_rows(paths: list[str | Path]) -> list[dict[str, Any]]:
    """Flatten benchmark JSON files into one row per measured pipeline stage."""
    rows: list[dict[str, Any]] = []
    for path in paths:
        benchmark_path = Path(path)
        try:
            payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Could not read benchmark JSON: {benchmark_path}") from error
        workload = payload.get("workload") or {}
        hardware = payload.get("platform") or {}
        for stage in payload.get("stages", []):
            rows.append(
                {
                    "benchmark": benchmark_path.name,
                    "photo_cat_version": payload.get("photo_cat_version"),
                    "stage": stage.get("stage"),
                    "status": stage.get("status"),
                    "duration_seconds": stage.get("duration_seconds"),
                    "peak_rss_mib": (
                        None if stage.get("rss_peak_bytes") is None else round(float(stage["rss_peak_bytes"]) / 1048576.0, 3)
                    ),
                    "python_peak_mib": round(float(stage.get("python_tracemalloc_peak_bytes", 0)) / 1048576.0, 3),
                    "catalogue_size_mib": (
                        None if workload.get("catalogue_size_bytes") is None else round(float(workload["catalogue_size_bytes"]) / 1048576.0, 3)
                    ),
                    "build_radius_arcsec": workload.get("max_build_radius_arcsec"),
                    "aperture_radius_arcsec": workload.get("aperture_radius_arcsec"),
                    "influence_radius_arcsec": workload.get("influence_radius_arcsec"),
                    "hardware": " / ".join(
                        str(value) for value in (hardware.get("system"), hardware.get("machine"), hardware.get("processor")) if value
                    ),
                    "logical_cpus": hardware.get("logical_cpu_count"),
                }
            )
    return rows


def write_benchmark_table(rows: list[dict[str, Any]], output_path: str | Path, output_format: str) -> str:
    """Write flattened benchmark rows as a Markdown or CSV table."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else ["benchmark", "stage", "duration_seconds"]
    if (output_format == "csv"):
        with destination.open("x", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return str(destination)
    if (output_format != "markdown"):
        raise ValueError("Benchmark table format must be markdown or csv.")
    labels = [name.replace("_", " ") for name in fieldnames]
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join("---" for _ in labels) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(name, "") if row.get(name) is not None else "") for name in fieldnames) + " |")
    destination.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(destination)
