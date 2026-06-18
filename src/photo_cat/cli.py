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
from typing import Iterator

from .cli_overrides import RuntimeConfigOverride, collect_overrides
from .path_policy import resolve_user_path


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config.yaml"


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
    """Run diagnostics with an explicit optional config path rather than an env mutation."""
    config_path = resolve_cli_config(args.config)

    from . import doctor

    return int(doctor.main(config_path) or 0)


def add_build_overrides(parser: argparse.ArgumentParser) -> None:
    """Register documented build/index CLI overrides."""
    build_group = parser.add_argument_group("build/index overrides")
    build_group.add_argument("--input-catalog", help="catalogue CSV path")
    build_group.add_argument("--out-dir", help="output/index directory for the build step")
    build_group.add_argument("--kdtree-filename", help="KDTree filename inside the output/index directory")
    build_group.add_argument("--usecolumns", "--use-columns", dest="usecolumns", help="legacy comma-separated column list: source_id,ra,dec,mag")
    build_group.add_argument("--catalog-source-id-column", help="catalogue source_id column name")
    build_group.add_argument("--ra-column", help="catalogue right-ascension column name")
    build_group.add_argument("--dec-column", help="catalogue declination column name")
    build_group.add_argument("--mag-column", "--phot-g-mean-mag-column", dest="phot_g_mean_mag_column", help="catalogue magnitude column name")
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
    query_group.add_argument("--field-of-view-arcsec", type=float, help="query field-of-view radius in arcseconds")
    query_group.add_argument("--delta-mag", type=float, help="maximum contaminant-target magnitude difference")


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
    parser = argparse.ArgumentParser(
        prog="photo-cat",
        description="PHOTO-CAT photometric contamination analysis tools.",
        formatter_class=OverrideHelpFormatter,
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

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="run diagnostic checks",
        formatter_class=OverrideHelpFormatter,
    )
    doctor_parser.add_argument("--config", help="optional configuration file for environment context")
    doctor_parser.set_defaults(func=run_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one CLI command and return a stable process status for expected user errors."""
    parser = build_parser()
    args = parser.parse_args(argv)

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
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if (__name__ == "__main__"):
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
