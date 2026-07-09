# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for result summaries, plots, reports, and benchmark CLI products."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from photo_cat import cli
from photo_cat import benchmark as benchmark_module
from photo_cat import build_neighbors_index, query_contamination_from_index
from photo_cat.result_products import (
    build_report,
    load_result_rows,
    summarize_results,
    write_export,
    write_matplotlib_plot,
)


def write_result_json(tmp_path: Path) -> Path:
    """Create a compact result file with both selected and all-neighbour metrics."""
    result_path = tmp_path / "result.json"
    result_path.write_text(
        json.dumps(
            [
                {
                    "source_id": "1001",
                    "ra": 10.0,
                    "dec": -5.0,
                    "phot_g_mean_mag": 10.0,
                    "flux_fraction_selected": 15.85,
                    "flux_fraction_all_neighbors": 16.85,
                    "flux_fraction_extra": 15.85,
                    "num_neighbors_in_radius": 2,
                    "num_contaminants_selected": 1,
                    "num_contaminants": 1,
                    "contaminants": [
                        {
                            "source_id": "1002",
                            "ra": 10.01,
                            "dec": -5.0,
                            "phot_g_mean_mag": 12.0,
                            "sep_arcsec": 12.5,
                        }
                    ],
                },
                {
                    "source_id": "1003",
                    "ra": 20.0,
                    "dec": 5.0,
                    "phot_g_mean_mag": 11.0,
                    "flux_fraction_selected": 0.0,
                    "flux_fraction_all_neighbors": 0.5,
                    "flux_fraction_extra": 0.0,
                    "num_neighbors_in_radius": 1,
                    "num_contaminants_selected": 0,
                    "num_contaminants": 0,
                    "contaminants": [],
                },
            ]
        ),
        encoding="utf-8",
    )
    return result_path


@pytest.mark.unit
def test_result_summary_preserves_selected_and_all_neighbor_fluxes(tmp_path: Path) -> None:
    """Summaries must keep the two contamination metrics distinct for paper statistics."""
    result_path = write_result_json(tmp_path)
    summary = summarize_results(load_result_rows(result_path), source_path=result_path)

    assert summary["target_count"] == 2
    assert summary["targets_with_contaminants"] == 1
    assert summary["total_selected_contaminants"] == 1
    assert summary["total_neighbors_in_radius"] == 3
    assert summary["selected_flux_fraction_percent"]["max"] == pytest.approx(15.85)
    assert summary["all_neighbor_flux_fraction_percent"]["max"] == pytest.approx(16.85)


@pytest.mark.regression
def test_cli_summarize_plot_and_report_create_reproducible_products(tmp_path: Path, capsys) -> None:
    """Public result-product commands should turn one JSON result into stats, SVG, and HTML."""
    result_path = write_result_json(tmp_path)

    assert cli.main(["summarize", str(result_path)]) == 0
    assert "PHOTO-CAT result summary" in capsys.readouterr().out

    summary_path = tmp_path / "summary.json"
    assert cli.main(["summarize", str(result_path), "--format", "json", "--output", str(summary_path)]) == 0
    assert json.loads(summary_path.read_text(encoding="utf-8"))["target_count"] == 2

    plot_path = tmp_path / "counts.svg"
    assert cli.main(["plot", str(result_path), "--kind", "contaminant-counts", "--output", str(plot_path)]) == 0
    assert "<svg" in plot_path.read_text(encoding="utf-8")

    report_path = tmp_path / "report.html"
    assert cli.main(["report", str(result_path), "--output", str(report_path)]) == 0
    assert "PHOTO-CAT report" in report_path.read_text(encoding="utf-8")

    export_path = tmp_path / "result.csv"
    assert cli.main(["export", str(result_path), "--output", str(export_path)]) == 0
    assert "contaminants_json" in export_path.read_text(encoding="utf-8")


@pytest.mark.regression
def test_cli_provenance_captures_catalogue_checksum_and_ranges(tmp_path: Path) -> None:
    """Catalogue provenance should preserve enough input facts for paper reproduction."""
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "source_id,ra,dec,phot_g_mean_mag\n"
        "1,10.0,-5.0,11.5\n"
        "1,12.0,,12.5\n"
        "2,20.0,6.0,13.5\n",
        encoding="utf-8",
    )
    adql_path = tmp_path / "selection.adql"
    adql_path.write_text("SELECT source_id FROM gaiadr3.gaia_source", encoding="utf-8")
    output_path = tmp_path / "provenance.json"

    assert cli.main([
        "provenance",
        str(catalog_path),
        "--adql-file",
        str(adql_path),
        "--output",
        str(output_path),
    ]) == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["catalogue"]["row_count"] == 3
    assert payload["catalogue"]["duplicate_source_id_count"] == 1
    assert payload["catalogue"]["null_counts"]["dec"] == 1
    assert payload["catalogue"]["numeric_ranges"]["ra"] == {"min": 10.0, "max": 20.0}
    assert payload["selection_query"]["sha256"]


@pytest.mark.unit
def test_export_parquet_and_markdown_report_are_available_for_notebooks(tmp_path: Path) -> None:
    """Tabular and Markdown products should be generated from the same result rows."""
    result_path = write_result_json(tmp_path)
    rows = load_result_rows(result_path)

    parquet_path = tmp_path / "result.parquet"
    assert write_export(rows, parquet_path, "parquet") == str(parquet_path)
    assert parquet_path.stat().st_size > 0

    report = build_report(rows, result_path, "markdown")
    assert "# PHOTO-CAT report" in report
    assert "PHOTO-CAT result summary" in report


@pytest.mark.unit
def test_optional_matplotlib_backend_writes_a_plot_when_installed(tmp_path: Path) -> None:
    """The richer plotting backend should work when matplotlib is available."""
    pytest.importorskip("matplotlib")
    result_path = write_result_json(tmp_path)
    rows = load_result_rows(result_path)
    plot_path = tmp_path / "flux.png"

    assert write_matplotlib_plot(rows, "flux", plot_path) == str(plot_path)
    assert plot_path.stat().st_size > 0


@pytest.mark.regression
def test_cli_benchmark_writes_timing_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The benchmark command should publish machine-readable timing metadata."""
    output_path = tmp_path / "benchmark.json"

    def fake_run_benchmark(config_path, *, run_build: bool, run_query: bool):
        return {
            "schema_version": 1,
            "photo_cat_version": "test",
            "config_path": None if config_path is None else str(config_path),
            "stages": [
                {
                    "stage": "query" if (run_query and not run_build) else "build-index",
                    "status": 0,
                    "duration_seconds": 0.001,
                    "python_tracemalloc_peak_bytes": 123,
                    "python_tracemalloc_current_bytes": 0,
                }
            ],
            "total_duration_seconds": 0.001,
            "ok": True,
        }

    monkeypatch.setattr(benchmark_module, "run_benchmark", fake_run_benchmark)

    assert cli.main(["benchmark", "--no-run-build", "--run-query", "--output", str(output_path)]) == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["stages"][0]["stage"] == "query"


@pytest.mark.unit
def test_benchmark_runner_records_stage_status_and_memory_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Benchmark internals should record stable timing and memory fields."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(build_neighbors_index, "main", lambda path: 0)
    monkeypatch.setattr(query_contamination_from_index, "main", lambda path: 0)

    payload = benchmark_module.run_benchmark(config_path, run_build=True, run_query=True)

    assert payload["ok"] is True
    assert [stage["stage"] for stage in payload["stages"]] == ["build-index", "query"]
    assert all("python_tracemalloc_peak_bytes" in stage for stage in payload["stages"])
    assert all("native_rss_available" in stage for stage in payload["stages"])
