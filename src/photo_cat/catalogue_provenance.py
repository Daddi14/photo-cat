# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Catalogue provenance capture for reproducible PHOTO-CAT analyses."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from . import __version__
from .index_manifest import atomic_write_json, sha256_file


PROVENANCE_SCHEMA_VERSION = 1


def _update_range(ranges: dict[str, dict[str, float | None]], column: str, value: str) -> None:
    text = value.strip()
    if (text == ""):
        return
    try:
        numeric_value = float(text)
    except ValueError:
        return
    current = ranges[column]
    current["min"] = numeric_value if current["min"] is None else min(current["min"], numeric_value)
    current["max"] = numeric_value if current["max"] is None else max(current["max"], numeric_value)


def build_catalogue_provenance(
    catalog_path: str | Path,
    *,
    adql_path: str | Path | None = None,
    source_id_column: str = "source_id",
    ra_column: str = "ra",
    dec_column: str = "dec",
    mag_column: str = "phot_g_mean_mag",
) -> dict[str, Any]:
    """Return a streaming provenance summary for one catalogue CSV."""
    path = Path(catalog_path).expanduser().resolve()
    if (not path.is_file()):
        raise FileNotFoundError(f"Catalogue CSV was not found: {path}")

    numeric_columns = [ra_column, dec_column, mag_column]
    null_counts: dict[str, int] = {}
    ranges: dict[str, dict[str, float | None]] = {column: {"min": None, "max": None} for column in numeric_columns}
    duplicate_examples: list[str] = []
    seen_ids: set[str] = set()
    duplicate_ids: set[str] = set()
    row_count = 0

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        header = list(reader.fieldnames or [])
        null_counts = {column: 0 for column in header}
        for row in reader:
            row_count += 1
            for column in header:
                if ((row.get(column) or "").strip() == ""):
                    null_counts[column] += 1
            for column in numeric_columns:
                if (column in row):
                    _update_range(ranges, column, row.get(column, ""))
            source_id = (row.get(source_id_column) or "").strip()
            if (source_id != ""):
                if (source_id in seen_ids and source_id not in duplicate_ids):
                    duplicate_ids.add(source_id)
                    if (len(duplicate_examples) < 10):
                        duplicate_examples.append(source_id)
                seen_ids.add(source_id)

    adql_payload = None
    if (adql_path is not None):
        query_path = Path(adql_path).expanduser().resolve()
        if (not query_path.is_file()):
            raise FileNotFoundError(f"ADQL/query file was not found: {query_path}")
        adql_payload = {
            "path": str(query_path),
            "sha256": sha256_file(query_path),
        }

    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "photo_cat_version": __version__,
        "catalogue": {
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "row_count": row_count,
            "columns": header,
            "null_counts": null_counts,
            "numeric_ranges": ranges,
            "source_id_column": source_id_column,
            "duplicate_source_id_count": len(duplicate_ids),
            "duplicate_source_id_examples": duplicate_examples,
        },
        "selection_query": adql_payload,
    }


def write_catalogue_provenance(payload: dict[str, Any], output_path: str | Path) -> str:
    """Write catalogue provenance JSON."""
    atomic_write_json(output_path, payload)
    return str(output_path)
