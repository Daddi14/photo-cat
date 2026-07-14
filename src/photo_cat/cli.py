#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Command-line interface for PHOTO-CAT."""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from contextlib import contextmanager
from importlib import import_module
from pathlib import Path
from typing import Iterator, NoReturn

from .cli_overrides import RuntimeConfigOverride, collect_overrides
from .i18n import SUPPORTED_LANGUAGES, initialize_language, tr
from .path_policy import resolve_user_path


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config.yaml"


class LocalizedArgumentParser(argparse.ArgumentParser):
    """Translate argparse-owned validation errors while preserving option names."""

    def format_usage(self) -> str:
        rendered = super().format_usage()
        return rendered.replace("usage:", tr("usage:"), 1)

    def format_help(self) -> str:
        rendered = super().format_help()
        return rendered.replace("usage:", tr("usage:"), 1)

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: {tr('ERROR')}: {tr(message)}\n")


def _option_value(argv: list[str], option: str) -> str | None:
    """Read a global value before argparse builds localized help."""
    for index, argument in enumerate(argv):
        if (argument == option and index + 1 < len(argv)):
            return argv[index + 1]
        if (argument.startswith(f"{option}=")):
            return argument.split("=", 1)[1]
    return None


def localize_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Translate argparse descriptions, group titles, and help recursively."""
    if (parser.description):
        parser.description = tr(parser.description)
    for group in parser._action_groups:
        group.title = tr(group.title)
        if (group.description):
            group.description = tr(group.description)
    for action in parser._actions:
        if (action.help and action.help is not argparse.SUPPRESS):
            action.help = tr(action.help)
        if (isinstance(action, argparse._SubParsersAction)):
            for child in dict.fromkeys(action.choices.values()):
                localize_parser(child)
    return parser


class OverrideHelpFormatter(argparse.HelpFormatter):
    """Argparse formatter used for readable CLI help output."""

    def __init__(self, prog: str):
        super().__init__(prog, max_help_position=42, width=110)


def resolve_cli_config(config_path: str | None) -> Path | None:
    """Resolve a CLI config path relative to the current working directory."""
    if (config_path is None):
        return DEFAULT_CONFIG_PATH.resolve() if (DEFAULT_CONFIG_PATH.is_file()) else None

    return resolve_user_path(config_path, Path.cwd())


@contextmanager
def scoped_config_environment(config_path: Path | None) -> Iterator[None]:
    """Temporarily expose a config path only for legacy GUI module initialization."""
    previous_value = os.environ.get("PHOTO_CAT_CONFIG")

    try:
        if (config_path is None):
            os.environ.pop("PHOTO_CAT_CONFIG", None)
        else:
            os.environ["PHOTO_CAT_CONFIG"] = str(config_path)
        yield
    finally:
        if (previous_value is None):
            os.environ.pop("PHOTO_CAT_CONFIG", None)
        else:
            os.environ["PHOTO_CAT_CONFIG"] = previous_value


def invoke_module_main(module_name: str, config_path: Path | None) -> int:
    """Import one CLI runtime module and pass its config path without global state."""
    module = import_module(f".{module_name}", package=__package__)
    return int(module.main(config_path) or 0)


def run_module_with_runtime_config(args: argparse.Namespace, module_name: str) -> int:
    """Execute one CLI stage with a disposable derived configuration when required."""
    config_path = resolve_cli_config(args.config)
    overrides = collect_overrides(args)

    with RuntimeConfigOverride(config_path, overrides) as runtime_config_path:
        return invoke_module_main(module_name, runtime_config_path)


def run_pipeline(args: argparse.Namespace) -> int:
    """Run the configured build/query pipeline."""
    return run_module_with_runtime_config(args, "config_and_run")


def run_build_index(args: argparse.Namespace) -> int:
    """Build a neighbour index using the configured or overridden inputs."""
    return run_module_with_runtime_config(args, "build_neighbors_index")


def run_query(args: argparse.Namespace) -> int:
    """Query contamination using the configured or overridden inputs."""
    return run_module_with_runtime_config(args, "query_contamination_from_index")


def run_configure(args: argparse.Namespace) -> int:
    """Run the legacy GUI inside a scoped environment without leaking config state."""
    config_path = resolve_cli_config(args.config)

    with scoped_config_environment(config_path):
        from . import configure_gui

        configure_gui = importlib.reload(configure_gui)
        return int(configure_gui.main() or 0)


def run_doctor(args: argparse.Namespace) -> int:
    """Run diagnostics with explicit config and output-mode selection."""
    config_path = resolve_cli_config(args.config)

    from . import doctor

    return int(doctor.main(config_path, args.format) or 0)


def run_summarize(args: argparse.Namespace) -> int:
    """Summarize a PHOTO-CAT query result JSON."""
    from .result_products import load_result_rows, summarize_results, write_summary

    rows = load_result_rows(args.result_json)
    summary = summarize_results(rows, source_path=args.result_json)
    rendered = write_summary(summary, args.output, args.format)
    if (args.output is None):
        print(rendered)
    else:
        print(tr("Summary saved to: {path}", path=rendered))
    return 0


def run_plot(args: argparse.Namespace) -> int:
    """Write an SVG, PNG, or PDF plot from a PHOTO-CAT query result JSON."""
    from .result_products import load_result_rows, write_matplotlib_plot, write_plot

    result_path = Path(args.result_json)
    requested_format = args.format
    if (requested_format is None):
        requested_format = "svg" if args.backend == "svg" else "png"
    output_path = Path(args.output) if args.output else result_path.with_name(f"{result_path.stem}_{args.kind}.{requested_format}")
    if (args.output and args.format and output_path.suffix.lower() != f".{requested_format}"):
        output_path = output_path.with_suffix(f".{requested_format}")
    rows = load_result_rows(result_path)
    backend = "matplotlib" if requested_format in {"png", "pdf"} else args.backend
    if (backend == "matplotlib"):
        saved_path = write_matplotlib_plot(rows, args.kind, output_path)
    else:
        saved_path = write_plot(rows, args.kind, output_path)
    print(tr("Plot saved to: {path}", path=saved_path))
    return 0


def run_publication_plots(args: argparse.Namespace) -> int:
    """Generate publication-oriented contamination plots."""
    from .publication_plots import generate_publication_plots

    payload = generate_publication_plots(
        args.result_json,
        args.output_dir,
        aperture_arcsec=args.aperture_arcsec,
        output_format=args.format,
        dpi=args.dpi,
    )
    print(tr("Publication plots saved under: {path}", path=args.output_dir))
    print(tr("Publication plot manifest saved to: {path}", path=payload["manifest_path"]))
    return 0


def run_report(args: argparse.Namespace) -> int:
    """Write an HTML or Markdown report from a PHOTO-CAT query result JSON."""
    from .result_products import load_result_rows, write_report

    result_path = Path(args.result_json)
    suffix = "md" if (args.format == "markdown") else args.format
    output_path = Path(args.output) if args.output else result_path.with_name(f"{result_path.stem}_report.{suffix}")
    rows = load_result_rows(result_path)
    saved_path = write_report(rows, result_path, output_path, args.format)
    print(tr("Report saved to: {path}", path=saved_path))
    return 0


def run_export(args: argparse.Namespace) -> int:
    """Export target-result rows to CSV or Parquet."""
    from .result_products import load_result_rows, write_export

    rows = load_result_rows(args.result_json)
    saved_path = write_export(rows, args.output, args.format)
    print(tr("Export saved to: {path}", path=saved_path))
    return 0


def run_screen(args: argparse.Namespace) -> int:
    """Rank targets and write explicit contamination-screening decisions."""
    from .result_products import load_result_rows
    from .result_screening import screen_results, write_screening

    rows = load_result_rows(args.result_json)
    payload = screen_results(
        rows,
        metric=args.metric,
        accept_max_percent=args.accept_max_percent,
        review_max_percent=args.review_max_percent,
        source_path=args.result_json,
    )
    saved_path = write_screening(payload, args.output, args.format)
    print(tr("Screening decisions saved to: {path}", path=saved_path))
    return 0


def run_validate_results(args: argparse.Namespace) -> int:
    """Compare PHOTO-CAT predictions with an external reference table."""
    from .reference_validation import validate_against_reference, write_validation
    from .result_products import load_result_rows

    rows = load_result_rows(args.result_json)
    payload, matched = validate_against_reference(
        rows,
        args.reference_csv,
        prediction_metric=args.metric,
        source_id_column=args.source_id_column,
        reference_column=args.reference_column,
        threshold_percent=args.threshold_percent,
    )
    saved_path, matched_path = write_validation(payload, args.output, matched, args.matched_output)
    print(tr("Validation statistics saved to: {path}", path=saved_path))
    if (matched_path is not None):
        print(tr("Matched validation rows saved to: {path}", path=matched_path))
    return 0


def run_provenance(args: argparse.Namespace) -> int:
    """Capture catalogue provenance metadata."""
    from .catalogue_provenance import build_catalogue_provenance, write_catalogue_provenance

    payload = build_catalogue_provenance(
        args.catalog_csv,
        adql_path=args.adql_file,
        source_id_column=args.source_id_column,
        ra_column=args.ra_column,
        dec_column=args.dec_column,
        mag_column=args.mag_column,
    )
    saved_path = write_catalogue_provenance(payload, args.output)
    print(tr("Provenance saved to: {path}", path=saved_path))
    return 0


def run_benchmark(args: argparse.Namespace) -> int:
    """Run selected pipeline stages and write benchmark metadata."""
    from .benchmark import run_benchmark as execute_benchmark
    from .benchmark import write_benchmark

    config_path = resolve_cli_config(args.config)
    overrides = collect_overrides(args)
    with RuntimeConfigOverride(config_path, overrides) as runtime_config_path:
        payload = execute_benchmark(
            runtime_config_path,
            run_build=args.benchmark_run_build,
            run_query=args.benchmark_run_query,
        )
    saved_path = write_benchmark(payload, args.output)
    print(tr("Benchmark saved to: {path}", path=saved_path))
    return 0 if payload["ok"] else 1


def run_benchmark_table(args: argparse.Namespace) -> int:
    """Render one or more benchmark JSON captures as a compact table."""
    from .benchmark import benchmark_table_rows, write_benchmark_table

    rows = benchmark_table_rows(args.benchmark_jsons)
    saved_path = write_benchmark_table(rows, args.output, args.format)
    print(tr("Benchmark table saved to: {path}", path=saved_path))
    return 0


def run_reproduce(args: argparse.Namespace) -> int:
    """Generate reproducible summaries, plots, reports, and a manifest."""
    from .reproducible_products import reproduce_products

    payload = reproduce_products(
        args.configs,
        args.result_jsons,
        args.output_dir,
        run_configs=args.run_configs,
        matplotlib=args.backend == "matplotlib",
    )
    print(tr("Reproduction manifest saved to: {path}", path=payload["manifest_path"]))
    return 0


def run_merge_bright_stars(args: argparse.Namespace) -> int:
    """Merge a base catalogue with a supplemental bright-star catalogue."""
    from .bright_star_merge import merge_catalogues

    payload = merge_catalogues(
        args.base_catalog,
        args.bright_catalog,
        args.output,
        source_id_column=args.source_id_column,
        prefer=args.prefer,
        provenance_output=args.provenance_output,
    )
    print(tr("Merged catalogue saved to: {path}", path=payload["output_catalog"]))
    if (args.provenance_output):
        print(tr("Merge provenance saved to: {path}", path=args.provenance_output))
    return 0


def add_build_overrides(parser: argparse.ArgumentParser) -> None:
    """Register documented build/index CLI overrides."""
    build_group = parser.add_argument_group("build/index overrides")
    build_group.add_argument("--input-catalog", help="catalogue CSV path")
    build_group.add_argument("--out-dir", help="output/index directory for the build step")
    build_group.add_argument("--usecolumns", "--use-columns", dest="usecolumns", help="legacy comma-separated column list: source_id,ra,dec,mag")
    build_group.add_argument("--catalog-source-id-column", help="catalogue source_id column name")
    build_group.add_argument("--ra-column", help="catalogue right-ascension column name")
    build_group.add_argument("--dec-column", help="catalogue declination column name")
    build_group.add_argument("--mag-column", "--phot-g-mean-mag-column", dest="phot_g_mean_mag_column", help="catalogue magnitude column name")
    build_group.add_argument(
        "--magnitude-columns",
        help="optional comma-separated band=column magnitude map, e.g. gaia_bp=phot_bp_mean_mag,gaia_rp=phot_rp_mean_mag",
    )
    build_group.add_argument("--use-dask", dest="use_dask", action=argparse.BooleanOptionalAction, default=None, help="enable or disable Dask catalogue loading")
    build_group.add_argument("--calculate-separations", dest="calculate_separations", action=argparse.BooleanOptionalAction, default=None, help="write neighbour separations during index building")
    build_group.add_argument("--max-radius-arcsec", type=float, help="maximum neighbour search radius in arcseconds")
    build_group.add_argument("--chunk-size", type=int, help="catalogue processing chunk size")
    build_group.add_argument("--buffer-flush-interval", type=int, help="row interval used when flushing neighbour buffers")


def add_query_overrides(parser: argparse.ArgumentParser) -> None:
    """Register documented query/contamination CLI overrides."""
    query_group = parser.add_argument_group("query/contamination overrides")
    query_group.add_argument("--index-dir", help="existing output/index directory used by the query step")
    query_group.add_argument("--targets-input", help="targets CSV path")
    query_group.add_argument("--no-targets-input", action="store_true", help="set TARGETS_INPUT to null and use --targets/manual targets")
    query_group.add_argument("--targets", help="comma-separated manual target source IDs")
    query_group.add_argument("--target-source-id-column", help="source_id column name in the targets CSV")
    query_group.add_argument(
        "--field-of-view-arcsec",
        "--aperture-radius-arcsec",
        dest="field_of_view_arcsec",
        type=float,
        help="circular extraction/screening aperture radius in arcseconds",
    )
    query_group.add_argument(
        "--influence-radius-arcsec",
        type=float,
        help="outer radius searched for weighted leakage; must cover the aperture",
    )
    query_group.add_argument("--delta-mag", type=float, help="maximum contaminant-target magnitude difference")
    query_group.add_argument(
        "--contamination-bands",
        help="comma-separated magnitude bands to compute; use all to query every band stored in the index",
    )
    query_group.add_argument(
        "--bandpass-transform-file",
        help="YAML profile for an empirical catalogue-to-mission band transformation",
    )
    query_group.add_argument(
        "--contamination-model-mode",
        choices=["top_hat", "radial_weight", "gaussian_psf", "gaussian_aperture"],
        help="aperture weighting model for flux metrics",
    )
    query_group.add_argument("--gaussian-fwhm-arcsec", type=float, help="Gaussian PSF FWHM when using gaussian_psf mode")
    query_group.add_argument("--radial-weight-file", help="CSV file with sep_arcsec,weight columns for radial_weight mode")
    query_group.add_argument(
        "--include-missing-targets",
        dest="include_missing_targets",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="include invalid/missing target IDs as status rows in query results",
    )


def add_execution_overrides(parser: argparse.ArgumentParser) -> None:
    """Register documented stage-selection CLI overrides."""
    execution_group = parser.add_argument_group("execution overrides")
    execution_group.add_argument("--run-build", dest="run_build", action=argparse.BooleanOptionalAction, default=None, help="enable or disable the build stage")
    execution_group.add_argument("--run-query", dest="run_query", action=argparse.BooleanOptionalAction, default=None, help="enable or disable the query stage")
    execution_group.add_argument("--replace-running-pipeline", dest="replace_running_pipeline", action=argparse.BooleanOptionalAction, default=None, help="replace an already-running launcher pipeline session")


def add_all_overrides(parser: argparse.ArgumentParser) -> None:
    """Register every override accepted by the full pipeline command."""
    add_build_overrides(parser)
    add_query_overrides(parser)
    add_execution_overrides(parser)


def build_parser() -> argparse.ArgumentParser:
    """Build the public PHOTO-CAT command parser."""
    parser = LocalizedArgumentParser(
        prog="photo-cat",
        description="PHOTO-CAT catalogue-level contamination risk-assessment and target-screening tools.",
        formatter_class=OverrideHelpFormatter,
    )
    parser.add_argument(
        "--language",
        choices=list(SUPPORTED_LANGUAGES),
        help="language used for help, messages, errors, and console output",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="show the installed PHOTO-CAT version and exit",
    )

    subparsers = parser.add_subparsers(dest="command")

    configure_parser = subparsers.add_parser(
        "configure",
        aliases=["gui"],
        help="open the graphical configurator",
        formatter_class=OverrideHelpFormatter,
    )
    configure_parser.add_argument("--config", help="configuration file to edit/use")
    configure_parser.set_defaults(func=run_configure)

    run_parser = subparsers.add_parser(
        "run",
        help="run the configured build/query pipeline",
        formatter_class=OverrideHelpFormatter,
    )
    run_parser.add_argument("--config", help="configuration file to use")
    add_all_overrides(run_parser)
    run_parser.set_defaults(func=run_pipeline)

    build_parser = subparsers.add_parser(
        "build-index",
        help="build the neighbour index from the configured catalogue",
        formatter_class=OverrideHelpFormatter,
    )
    build_parser.add_argument("--config", help="configuration file to use")
    add_build_overrides(build_parser)
    build_parser.set_defaults(func=run_build_index)

    query_parser = subparsers.add_parser(
        "query",
        help="query contamination from an existing neighbour index",
        formatter_class=OverrideHelpFormatter,
    )
    query_parser.add_argument("--config", help="configuration file to use")
    add_query_overrides(query_parser)
    query_parser.set_defaults(func=run_query)

    summarize_parser = subparsers.add_parser(
        "summarize",
        aliases=["summary"],
        help="summarize a PHOTO-CAT query result JSON",
        formatter_class=OverrideHelpFormatter,
    )
    summarize_parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    summarize_parser.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        help="summary output format (default: text)",
    )
    summarize_parser.add_argument("--output", help="optional output path")
    summarize_parser.set_defaults(func=run_summarize)

    plot_parser = subparsers.add_parser(
        "plot",
        help="write an SVG, PNG, or PDF plot from a PHOTO-CAT query result JSON",
        formatter_class=OverrideHelpFormatter,
    )
    plot_parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    plot_parser.add_argument(
        "--kind",
        choices=[
            "contaminant-counts",
            "flux",
            "separations",
            "flux-vs-separation",
            "contamination-vs-magnitude",
            "sky-map",
        ],
        default="contaminant-counts",
        help="plot type (default: contaminant-counts)",
    )
    plot_parser.add_argument(
        "--format",
        choices=["svg", "png", "pdf"],
        default=None,
        help="plot output format; PNG and PDF use matplotlib",
    )
    plot_parser.add_argument(
        "--backend",
        choices=["svg", "matplotlib"],
        default="svg",
        help="plot backend (default: svg)",
    )
    plot_parser.add_argument("--output", help="plot output path")
    plot_parser.set_defaults(func=run_plot)

    publication_plots_parser = subparsers.add_parser(
        "publication-plots",
        help="generate contamination distributions and an accessible sky map",
        formatter_class=OverrideHelpFormatter,
    )
    publication_plots_parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    publication_plots_parser.add_argument("--aperture-arcsec", type=float, required=True, help="aperture represented by the result")
    publication_plots_parser.add_argument("--output-dir", required=True, help="directory for plots and manifest")
    publication_plots_parser.add_argument("--format", choices=["png", "pdf", "svg"], default="png")
    publication_plots_parser.add_argument("--dpi", type=int, default=300, help="raster resolution (default: 300)")
    publication_plots_parser.set_defaults(func=run_publication_plots)

    export_parser = subparsers.add_parser(
        "export",
        help="export a PHOTO-CAT query result JSON to CSV or Parquet",
        formatter_class=OverrideHelpFormatter,
    )
    export_parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    export_parser.add_argument("--output", required=True, help="export output path")
    export_parser.add_argument(
        "--format",
        choices=["csv", "parquet"],
        default="csv",
        help="export format (default: csv)",
    )
    export_parser.set_defaults(func=run_export)

    screen_parser = subparsers.add_parser(
        "screen",
        aliases=["rank"],
        help="rank targets and assign contamination-screening decisions",
        formatter_class=OverrideHelpFormatter,
    )
    screen_parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    screen_parser.add_argument("--output", required=True, help="screening output path")
    screen_parser.add_argument("--format", choices=["json", "csv", "markdown"], default="csv")
    screen_parser.add_argument(
        "--metric",
        default="flux_fraction_total_weighted",
        help="result metric used as the risk score",
    )
    screen_parser.add_argument("--accept-max-percent", type=float, default=5.0)
    screen_parser.add_argument("--review-max-percent", type=float, default=20.0)
    screen_parser.set_defaults(func=run_screen)

    validate_parser = subparsers.add_parser(
        "validate-results",
        aliases=["validate"],
        help="compare PHOTO-CAT predictions with a reference contamination table",
        formatter_class=OverrideHelpFormatter,
    )
    validate_parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    validate_parser.add_argument("reference_csv", help="reference contamination CSV")
    validate_parser.add_argument("--output", required=True, help="validation statistics JSON")
    validate_parser.add_argument("--matched-output", help="optional matched residual CSV")
    validate_parser.add_argument("--metric", default="flux_fraction_total_weighted")
    validate_parser.add_argument("--source-id-column", default="source_id")
    validate_parser.add_argument("--reference-column", default="contamination_percent")
    validate_parser.add_argument("--threshold-percent", type=float)
    validate_parser.set_defaults(func=run_validate_results)

    report_parser = subparsers.add_parser(
        "report",
        help="write an HTML, Markdown, or PDF report from a PHOTO-CAT query result JSON",
        formatter_class=OverrideHelpFormatter,
    )
    report_parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    report_parser.add_argument(
        "--format",
        choices=["html", "markdown", "pdf"],
        default="html",
        help="report format (default: html)",
    )
    report_parser.add_argument("--output", help="report output path")
    report_parser.set_defaults(func=run_report)

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="run selected stages and write benchmark metadata",
        formatter_class=OverrideHelpFormatter,
    )
    benchmark_parser.add_argument("--config", help="configuration file to use")
    benchmark_parser.add_argument("--output", required=True, help="benchmark JSON output path")
    benchmark_parser.add_argument(
        "--run-build",
        dest="benchmark_run_build",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include or skip the build stage",
    )
    benchmark_parser.add_argument(
        "--run-query",
        dest="benchmark_run_query",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="include or skip the query stage",
    )
    add_build_overrides(benchmark_parser)
    add_query_overrides(benchmark_parser)
    benchmark_parser.set_defaults(func=run_benchmark)

    benchmark_table_parser = subparsers.add_parser(
        "benchmark-table",
        help="render benchmark JSON captures as a Markdown or CSV table",
        formatter_class=OverrideHelpFormatter,
    )
    benchmark_table_parser.add_argument("benchmark_jsons", nargs="+", help="benchmark JSON file(s)")
    benchmark_table_parser.add_argument("--output", required=True, help="table output path")
    benchmark_table_parser.add_argument("--format", choices=["markdown", "csv"], default="markdown")
    benchmark_table_parser.set_defaults(func=run_benchmark_table)

    reproduce_parser = subparsers.add_parser(
        "reproduce",
        help="generate reproducible summaries, plots, reports, and a manifest",
        formatter_class=OverrideHelpFormatter,
    )
    reproduce_parser.add_argument(
        "--config",
        dest="configs",
        action="append",
        default=[],
        help="run configuration file; may be provided multiple times",
    )
    reproduce_parser.add_argument(
        "--result-json",
        dest="result_jsons",
        action="append",
        default=[],
        help="existing result JSON to include; may be provided multiple times",
    )
    reproduce_parser.add_argument("--output-dir", required=True, help="directory for manifest and generated products")
    reproduce_parser.add_argument(
        "--run-configs",
        action="store_true",
        help="run each provided config before collecting the latest result JSON",
    )
    reproduce_parser.add_argument(
        "--backend",
        choices=["svg", "matplotlib"],
        default="svg",
        help="plot backend for generated products (default: svg)",
    )
    reproduce_parser.set_defaults(func=run_reproduce)

    merge_parser = subparsers.add_parser(
        "merge-bright-stars",
        help="merge a Gaia-like catalogue with a supplemental bright-star table",
        formatter_class=OverrideHelpFormatter,
    )
    merge_parser.add_argument("base_catalog", help="base Gaia-like catalogue CSV")
    merge_parser.add_argument("bright_catalog", help="supplemental bright-star catalogue CSV")
    merge_parser.add_argument("--output", required=True, help="merged catalogue CSV path")
    merge_parser.add_argument("--source-id-column", default="source_id", help="source ID column shared by both CSVs")
    merge_parser.add_argument("--prefer", choices=["bright", "base"], default="bright", help="which table wins duplicate source IDs")
    merge_parser.add_argument("--provenance-output", help="optional JSON metadata path for the merge")
    merge_parser.set_defaults(func=run_merge_bright_stars)

    provenance_parser = subparsers.add_parser(
        "provenance",
        help="write catalogue provenance metadata",
        formatter_class=OverrideHelpFormatter,
    )
    provenance_parser.add_argument("catalog_csv", help="catalogue CSV path")
    provenance_parser.add_argument("--output", required=True, help="provenance JSON output path")
    provenance_parser.add_argument("--adql-file", help="optional ADQL/query file used to create the catalogue")
    provenance_parser.add_argument("--source-id-column", default="source_id", help="source ID column name")
    provenance_parser.add_argument("--ra-column", default="ra", help="right-ascension column name")
    provenance_parser.add_argument("--dec-column", default="dec", help="declination column name")
    provenance_parser.add_argument("--mag-column", default="phot_g_mean_mag", help="magnitude column name")
    provenance_parser.set_defaults(func=run_provenance)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="run diagnostic checks",
        formatter_class=OverrideHelpFormatter,
    )
    doctor_parser.add_argument("--config", help="optional configuration file for environment context")
    doctor_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="diagnostic output format (default: text)",
    )
    doctor_parser.set_defaults(func=run_doctor)

    return localize_parser(parser)


def main(argv: list[str] | None = None) -> int:
    """Run one CLI command and return a stable process status for expected user errors."""
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    explicit_language = _option_value(effective_argv, "--language")
    config_value = _option_value(effective_argv, "--config")
    initialize_language(resolve_cli_config(config_value), explicit_language)
    parser = build_parser()
    args = parser.parse_args(effective_argv)

    if (args.version):
        from . import __version__

        print(__version__)
        return 0

    if (not hasattr(args, "func")):
        parser.print_help()
        return 0

    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        raise
    except Exception as error:
        print(f"{tr('ERROR')}: {tr(error)}", file=sys.stderr)
        return 1


if (__name__ == "__main__"):
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
