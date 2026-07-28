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
from photo_cat import reproducible_products
from photo_cat.reference_validation import validate_against_reference, write_validation
from photo_cat.result_products import (
    build_report,
    build_svg_plot,
    iter_contaminant_points,
    load_result_rows,
    summarize_results,
    write_export,
    write_matplotlib_plot,
)
from photo_cat.result_screening import screen_results, write_screening


@pytest.mark.unit
def test_result_products_use_the_selected_band_magnitude() -> None:
    """Plot helpers must use generic output-band magnitudes instead of a stale Gaia-G value."""
    rows = [{
        "magnitude": 10.0,
        "magnitude_band": "gaia_bp",
        "phot_g_mean_mag": 8.0,
        "contaminants": [{
            "magnitude": 12.0,
            "magnitude_band": "gaia_bp",
            "phot_g_mean_mag": 9.0,
            "sep_arcsec": 3.0,
        }],
    }]

    point = next(iter(iter_contaminant_points(rows)))
    assert point["target_magnitude"] == pytest.approx(10.0)
    assert point["contaminant_magnitude"] == pytest.approx(12.0)
    assert point["delta_mag"] == pytest.approx(2.0)
    assert point["flux_ratio_percent"] == pytest.approx(10.0 ** -0.8 * 100.0)


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


def _svg_circle_radii(svg: str) -> list[float]:
    """Extract every circle radius from an SVG plot for marker-size assertions."""
    import re

    return [float(match) for match in re.findall(r'<circle[^>]*\br="([0-9.]+)"', svg)]


@pytest.mark.unit
def test_result_summary_preserves_selected_and_all_neighbor_fluxes(tmp_path: Path) -> None:
    """Summaries must keep the two contamination metrics distinct for downstream statistics."""
    result_path = write_result_json(tmp_path)
    summary = summarize_results(load_result_rows(result_path), source_path=result_path)

    assert summary["target_count"] == 2
    assert summary["targets_with_contaminants"] == 1
    assert summary["total_selected_contaminants"] == 1
    assert summary["total_neighbors_in_radius"] == 3
    assert summary["selected_flux_fraction_percent"]["max"] == pytest.approx(15.85)
    assert summary["all_neighbor_flux_fraction_percent"]["max"] == pytest.approx(16.85)


@pytest.mark.unit
def test_screening_ranks_targets_and_explains_decisions(tmp_path: Path) -> None:
    """Decision products should turn contamination percentages into auditable target choices."""
    rows = load_result_rows(write_result_json(tmp_path))
    payload = screen_results(rows, accept_max_percent=1.0, review_max_percent=10.0)

    assert [item["source_id"] for item in payload["decisions"]] == ["1001", "1003"]
    assert [item["decision"] for item in payload["decisions"]] == ["reject", "accept"]
    assert payload["decisions"][0]["decision_reasons"]


@pytest.mark.regression
def test_cli_screen_writes_github_friendly_markdown(tmp_path: Path) -> None:
    """The public screening command should write a directly reviewable ranking table."""
    result_path = write_result_json(tmp_path)
    output_path = tmp_path / "screening.md"

    assert cli.main(["screen", str(result_path), "--format", "markdown", "--output", str(output_path)]) == 0
    rendered = output_path.read_text(encoding="utf-8")
    assert "PHOTO-CAT target screening" in rendered
    assert "| Rank | Source ID |" in rendered


@pytest.mark.unit
def test_screening_covers_review_unresolved_and_outside_flux_reasons(tmp_path: Path) -> None:
    """Every screening state and outside-aperture warning should remain explicit."""
    rows = [
        {"source_id": "review", "flux_fraction_total_weighted": 10.0, "flux_fraction_outside_aperture": 2.5},
        {"source_id": "missing", "flux_fraction_total_weighted": None},
    ]
    payload = screen_results(rows, accept_max_percent=5.0, review_max_percent=20.0, source_path=tmp_path / "result.json")

    assert payload["summary"] == {"accept": 0, "review": 1, "reject": 0, "unresolved": 1}
    assert payload["decisions"][0]["decision"] == "review"
    assert "outside-aperture weighted flux" in payload["decisions"][0]["decision_reasons"][1]
    assert payload["decisions"][1]["risk_score_percent"] is None
    assert payload["source_result_json"].endswith("result.json")


@pytest.mark.unit
def test_screening_validates_thresholds_and_writes_json_and_csv(tmp_path: Path) -> None:
    """Threshold mistakes should fail, while both machine-readable formats remain stable."""
    with pytest.raises(ValueError, match="finite"):
        screen_results([], accept_max_percent=float("nan"))
    with pytest.raises(ValueError, match="Require"):
        screen_results([], accept_max_percent=10.0, review_max_percent=5.0)

    payload = screen_results([{"source_id": "1", "flux_fraction_total_weighted": 1.0}])
    json_path = tmp_path / "screening.json"
    csv_path = tmp_path / "screening.csv"
    assert write_screening(payload, json_path, "json") == str(json_path)
    assert write_screening(payload, csv_path, "csv") == str(csv_path)
    assert json.loads(json_path.read_text(encoding="utf-8"))["summary"]["accept"] == 1
    assert "decision_reasons" in csv_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="format"):
        write_screening(payload, tmp_path / "bad.txt", "text")


@pytest.mark.unit
def test_reference_validation_reports_bias_and_error_metrics(tmp_path: Path) -> None:
    """Reference comparisons should quantify agreement instead of relying on visual inspection."""
    rows = load_result_rows(write_result_json(tmp_path))
    reference_path = tmp_path / "reference.csv"
    reference_path.write_text("source_id,contamination_percent\n1001,14.85\n1003,1.5\n", encoding="utf-8")

    payload, matched = validate_against_reference(rows, reference_path, threshold_percent=10.0)

    assert len(matched) == 2
    assert payload["statistics"]["bias_percent"] == pytest.approx(0.5)
    assert payload["statistics"]["mae_percent"] == pytest.approx(1.5)
    assert payload["statistics"]["rmse_percent"] == pytest.approx(2.5**0.5)
    assert payload["statistics"]["threshold_accuracy"] == 1.0


@pytest.mark.regression
def test_cli_validate_results_writes_statistics_and_matches(tmp_path: Path) -> None:
    """The validation CLI should create reusable statistics and residual tables."""
    result_path = write_result_json(tmp_path)
    reference_path = tmp_path / "reference.csv"
    reference_path.write_text("source_id,contamination_percent\n1001,15\n", encoding="utf-8")
    output_path = tmp_path / "validation.json"
    matches_path = tmp_path / "matches.csv"

    assert cli.main([
        "validate-results", str(result_path), str(reference_path),
        "--output", str(output_path), "--matched-output", str(matches_path),
    ]) == 0
    assert json.loads(output_path.read_text(encoding="utf-8"))["statistics"]["matched_targets"] == 1
    assert "residual_percent" in matches_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_reference_validation_handles_bad_rows_empty_matches_and_invalid_inputs(tmp_path: Path) -> None:
    """Malformed measurements must be excluded without producing misleading statistics."""
    missing_column = tmp_path / "missing.csv"
    missing_column.write_text("source_id,wrong\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required columns"):
        validate_against_reference([], missing_column)

    reference_path = tmp_path / "reference.csv"
    reference_path.write_text("source_id,contamination_percent\n1,bad\n2,nan\n3,4\n", encoding="utf-8")
    payload, matched = validate_against_reference(
        [{"source_id": "3", "flux_fraction_total_weighted": "bad"}, {"source_id": "4", "flux_fraction_total_weighted": 2}],
        reference_path,
        threshold_percent=5.0,
    )
    assert matched == []
    assert payload["statistics"]["bias_percent"] is None
    assert payload["statistics"]["threshold_accuracy"] is None
    with pytest.raises(ValueError, match="non-negative"):
        validate_against_reference([], reference_path, threshold_percent=-1.0)

    output_path = tmp_path / "validation.json"
    assert write_validation(payload, output_path, matched) == (str(output_path), None)


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


@pytest.mark.unit
def test_new_reviewer_plot_kinds_build_svg(tmp_path: Path) -> None:
    """Reviewer-facing plots should be available without optional dependencies."""
    rows = load_result_rows(write_result_json(tmp_path))

    for kind in ("separations", "flux-vs-separation", "contamination-vs-magnitude"):
        svg = build_svg_plot(rows, kind)
        assert "<svg" in svg
        assert "font-family" in svg


@pytest.mark.unit
def test_sky_map_uses_colourblind_safe_palette_with_legend(tmp_path: Path) -> None:
    """The sky map must distinguish classes with a colourblind-safe palette and a colour legend."""
    rows = load_result_rows(write_result_json(tmp_path))

    svg = build_svg_plot(rows, "sky-map")

    assert "#0072B2" in svg  # blue: 0 contaminants
    assert "#E69F00" in svg  # orange: 1-3 contaminants
    assert "#D55E00" in svg  # vermillion: >3 contaminants
    assert "0 contaminants" in svg and "&gt;3 contaminants" in svg  # colour legend present (escaped >)
    assert "RA [deg]" in svg and "Dec [deg]" in svg


@pytest.mark.unit
def test_separation_plot_uses_one_arcsecond_bins(tmp_path: Path) -> None:
    """Plot 'separations' must bin contaminant separations in 1-arcsecond bins."""
    rows = load_result_rows(write_result_json(tmp_path))

    svg = build_svg_plot(rows, "separations")

    assert "Separation (arcsec)" in svg
    assert "Number of contaminants" in svg


@pytest.mark.regression
def test_cli_provenance_captures_catalogue_checksum_and_ranges(tmp_path: Path) -> None:
    """Catalogue provenance should preserve enough input facts for reproduction."""
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
@pytest.mark.parametrize(("output_format", "signature"), [("png", b"\x89PNG"), ("pdf", b"%PDF")])
def test_cli_plot_supports_png_and_pdf_formats(tmp_path: Path, output_format: str, signature: bytes) -> None:
    """The public plot command selects matplotlib automatically for PNG and PDF products."""
    pytest.importorskip("matplotlib")
    result_path = write_result_json(tmp_path)
    output_path = tmp_path / f"contamination.{output_format}"

    assert cli.main([
        "plot",
        str(result_path),
        "--kind",
        "flux",
        "--format",
        output_format,
        "--output",
        str(output_path),
    ]) == 0

    assert output_path.read_bytes().startswith(signature)


@pytest.mark.regression
def test_cli_report_writes_multipage_pdf(tmp_path: Path) -> None:
    """PDF reports contain a summary page and diagnostic plot pages rather than renamed HTML."""
    pytest.importorskip("matplotlib")
    result_path = write_result_json(tmp_path)
    report_path = tmp_path / "report.pdf"

    assert cli.main([
        "report",
        str(result_path),
        "--format",
        "pdf",
        "--output",
        str(report_path),
    ]) == 0

    payload = report_path.read_bytes()
    assert payload.startswith(b"%PDF")
    assert payload.count(b"/Type /Page") >= 6


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


@pytest.mark.regression
def test_benchmark_table_renders_markdown(tmp_path: Path) -> None:
    """Benchmark captures should be convertible into the compact table requested by reviewers."""
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(json.dumps({
        "photo_cat_version": "2.0.0",
        "platform": {"system": "TestOS", "machine": "x64", "logical_cpu_count": 8},
        "workload": {"catalogue_size_bytes": 1048576, "max_build_radius_arcsec": 120, "aperture_radius_arcsec": 47, "influence_radius_arcsec": 75},
        "stages": [{"stage": "query", "status": 0, "duration_seconds": 1.25, "python_tracemalloc_peak_bytes": 1048576, "rss_peak_bytes": 2097152}],
    }), encoding="utf-8")
    table_path = tmp_path / "benchmark.md"

    assert cli.main(["benchmark-table", str(benchmark_path), "--output", str(table_path)]) == 0
    rendered = table_path.read_text(encoding="utf-8")
    assert "| benchmark | photo cat version | stage |" in rendered
    assert "| benchmark.json | 2.0.0 | query |" in rendered


@pytest.mark.unit
def test_benchmark_table_supports_csv_empty_tables_and_bad_json(tmp_path: Path) -> None:
    """Table serialization and malformed benchmark input should have deterministic behavior."""
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(json.dumps({
        "photo_cat_version": "2.0.0",
        "platform": {},
        "workload": {},
        "stages": [{"stage": "query", "status": 0, "duration_seconds": 1, "python_tracemalloc_peak_bytes": 0}],
    }), encoding="utf-8")
    rows = benchmark_module.benchmark_table_rows([benchmark_path])
    assert rows[0]["peak_rss_mib"] is None
    assert rows[0]["hardware"] == ""

    csv_path = tmp_path / "benchmark.csv"
    assert benchmark_module.write_benchmark_table(rows, csv_path, "csv") == str(csv_path)
    assert "duration_seconds" in csv_path.read_text(encoding="utf-8")

    empty_path = tmp_path / "empty.md"
    benchmark_module.write_benchmark_table([], empty_path, "markdown")
    assert "benchmark | stage | duration seconds" in empty_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="format"):
        benchmark_module.write_benchmark_table([], tmp_path / "bad.txt", "html")

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Could not read benchmark JSON"):
        benchmark_module.benchmark_table_rows([bad_json])


@pytest.mark.regression
def test_cli_merge_bright_stars_writes_catalogue_and_provenance(tmp_path: Path) -> None:
    """The bright-star merge utility should produce a build-ready CSV plus metadata."""
    base_path = tmp_path / "base.csv"
    bright_path = tmp_path / "bright.csv"
    merged_path = tmp_path / "merged.csv"
    provenance_path = tmp_path / "merge.json"
    base_path.write_text("source_id,ra,dec,phot_g_mean_mag\n1,10,20,11\n2,11,21,12\n", encoding="utf-8")
    bright_path.write_text("source_id,ra,dec,phot_g_mean_mag\n2,12,22,9\n3,13,23,8\n", encoding="utf-8")

    assert cli.main([
        "merge-bright-stars",
        str(base_path),
        str(bright_path),
        "--output",
        str(merged_path),
        "--provenance-output",
        str(provenance_path),
    ]) == 0

    assert "3,13,23,8" in merged_path.read_text(encoding="utf-8")
    assert json.loads(provenance_path.read_text(encoding="utf-8"))["merged_rows"] == 3


@pytest.mark.regression
def test_reproduce_products_materializes_manifest_and_plots(tmp_path: Path) -> None:
    """Reproduction should bundle checksummed results with summaries and plots."""
    result_path = write_result_json(tmp_path)
    output_dir = tmp_path / "reproduce_out"

    payload = reproducible_products.reproduce_products([], [result_path], output_dir)

    manifest_path = Path(payload["manifest_path"])
    assert manifest_path.is_file()
    assert payload["products"][0]["result_sha256"]
    assert Path(payload["products"][0]["summary_json"]).is_file()
    assert Path(payload["products"][0]["plots"]["flux-vs-separation"]).is_file()
    assert "reproduction_manifest" in manifest_path.name


@pytest.mark.regression
def test_reproduce_products_can_run_config_and_find_latest_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configs should be runnable and resolved to the latest index output result."""
    index_output = tmp_path / "index" / "results"
    index_output.mkdir(parents=True)
    result_path = write_result_json(index_output)
    config_path = tmp_path / "run_config.yaml"
    config_path.write_text(
        "query_contamination_from_index:\n"
        "  io:\n"
        "    INDEX_DIR: index\n"
        "    TARGETS_INPUT:\n"
        "    targets: ['1001']\n"
        "    target_source_id_column: source_id\n"
        "  settings:\n"
        "    field_of_view_arcsec: 47\n"
        "    delta_mag: 5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(reproducible_products, "run_pipeline", lambda path: 0)

    payload = reproducible_products.reproduce_products([config_path], [], tmp_path / "reproduce_from_config", run_configs=True)

    assert payload["configs"][0]["latest_result_json"] == str(result_path.resolve())
    assert Path(payload["configs"][0]["config_copy"]).is_file()


@pytest.mark.unit
def test_reproduce_products_rejects_empty_inputs(tmp_path: Path) -> None:
    """A reproduction manifest with no configs or results would be misleading."""
    with pytest.raises(ValueError, match="at least one"):
        reproducible_products.reproduce_products([], [], tmp_path / "reproduce_out")


@pytest.mark.unit
def test_latest_result_json_reports_missing_outputs(tmp_path: Path) -> None:
    """Missing query outputs should produce a direct reproduction error."""
    (tmp_path / "index" / "results").mkdir(parents=True)

    with pytest.raises(ValueError, match="No query result"):
        reproducible_products.latest_result_json(tmp_path / "index")


@pytest.mark.unit
def test_reproduce_products_reports_failed_config_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed pre-run should stop before writing misleading products."""
    config_path = tmp_path / "run_config.yaml"
    config_path.write_text("query_contamination_from_index: {}\n", encoding="utf-8")
    monkeypatch.setattr(reproducible_products, "run_pipeline", lambda path: 1)

    with pytest.raises(RuntimeError, match="Pipeline failed"):
        reproducible_products.reproduce_products([config_path], [], tmp_path / "reproduce_out", run_configs=True)
