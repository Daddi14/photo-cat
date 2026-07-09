#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Generate paper-style summary, plots, and report from a PHOTO-CAT result JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = PROJECT_ROOT / "src"
if SOURCE_DIR.is_dir() and str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from photo_cat.result_products import (  # noqa: E402
    PLOT_KINDS,
    load_result_rows,
    summarize_results,
    write_plot,
    write_report,
    write_summary,
)


def build_parser() -> argparse.ArgumentParser:
    """Create the example-script argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("result_json", help="PHOTO-CAT query result JSON")
    parser.add_argument(
        "--out-dir",
        default="paper_products",
        help="directory for generated products (default: paper_products)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Generate reproducibility products from one result JSON."""
    args = build_parser().parse_args(argv)
    result_path = Path(args.result_json)
    output_dir = Path(args.out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_result_rows(result_path)
    summary = summarize_results(rows, source_path=result_path)
    write_summary(summary, output_dir / "summary.json", "json")
    write_summary(summary, output_dir / "summary.csv", "csv")
    write_summary(summary, output_dir / "summary.txt", "text")

    for kind in PLOT_KINDS:
        write_plot(rows, kind, output_dir / f"{kind}.svg")

    write_report(rows, result_path, output_dir / "report.html", "html")
    write_report(rows, result_path, output_dir / "report.md", "markdown")

    print(f"Paper-style products written to: {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
