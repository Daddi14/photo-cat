#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Command-line interface for PHOTO-CAT."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_DIR / "config.yaml"


def resolve_cli_config(config_path: str | None) -> Path:
    """Resolve a CLI config path relative to the current working directory."""
    if (config_path is None):
        return DEFAULT_CONFIG_PATH.resolve()

    path = Path(os.path.expanduser(config_path))
    if (not path.is_absolute()):
        path = Path.cwd() / path

    return path.resolve()


def set_config_environment(config_path: str | None) -> Path:
    """Set PHOTO_CAT_CONFIG for command modules that load the runtime config."""
    resolved = resolve_cli_config(config_path)
    os.environ["PHOTO_CAT_CONFIG"] = str(resolved)
    return resolved


def run_pipeline(args: argparse.Namespace) -> int:
    set_config_environment(args.config)
    from . import config_and_run

    return config_and_run.main()


def run_build_index(args: argparse.Namespace) -> int:
    set_config_environment(args.config)
    from . import build_neighbors_index

    return build_neighbors_index.main()


def run_query(args: argparse.Namespace) -> int:
    set_config_environment(args.config)
    from . import query_contamination_from_index

    return query_contamination_from_index.main()


def run_configure(args: argparse.Namespace) -> int:
    if (args.config is not None):
        set_config_environment(args.config)

    from . import configure_gui

    return configure_gui.main()


def run_doctor(args: argparse.Namespace) -> int:
    if (args.config is not None):
        set_config_environment(args.config)

    from . import doctor

    return doctor.main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="photo-cat",
        description="PHOTO-CAT photometric contamination analysis tools.",
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
    )
    configure_parser.add_argument("--config", help="configuration file to edit/use")
    configure_parser.set_defaults(func=run_configure)

    run_parser = subparsers.add_parser(
        "run",
        help="run the configured build/query pipeline",
    )
    run_parser.add_argument("--config", help="configuration file to use")
    run_parser.set_defaults(func=run_pipeline)

    build_parser = subparsers.add_parser(
        "build-index",
        help="build the neighbour index from the configured catalogue",
    )
    build_parser.add_argument("--config", help="configuration file to use")
    build_parser.set_defaults(func=run_build_index)

    query_parser = subparsers.add_parser(
        "query",
        help="query contamination from an existing neighbour index",
    )
    query_parser.add_argument("--config", help="configuration file to use")
    query_parser.set_defaults(func=run_query)

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="run diagnostic checks",
    )
    doctor_parser.add_argument("--config", help="optional configuration file for environment context")
    doctor_parser.set_defaults(func=run_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if (args.version):
        from . import __version__

        print(__version__)
        return 0

    if (not hasattr(args, "func")):
        parser.print_help()
        return 0

    return int(args.func(args) or 0)


if (__name__ == "__main__"):
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
