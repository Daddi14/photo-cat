# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Merge a Gaia-like catalogue with a supplemental bright-star table."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .index_manifest import atomic_write_json, sha256_file


def _read_csv(path: str | Path, label: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, dtype={"source_id": "object"})
    except Exception as error:
        raise ValueError(f"Could not read {label} CSV: {path}") from error


def merge_catalogues(
    base_catalog: str | Path,
    bright_catalog: str | Path,
    output_path: str | Path,
    *,
    source_id_column: str = "source_id",
    prefer: str = "bright",
    provenance_output: str | Path | None = None,
) -> dict[str, Any]:
    """Append bright stars, de-duplicate source IDs, and write a merged CSV."""
    if (prefer not in {"bright", "base"}):
        raise ValueError("prefer must be either bright or base.")

    base = _read_csv(base_catalog, "base catalogue")
    bright = _read_csv(bright_catalog, "bright-star catalogue")
    for label, dataframe in (("base catalogue", base), ("bright-star catalogue", bright)):
        if (source_id_column not in dataframe.columns):
            raise ValueError(f"{label} is missing source ID column: {source_id_column}")
        dataframe[source_id_column] = dataframe[source_id_column].astype(str)

    base["_photo_cat_source_table"] = "base"
    bright["_photo_cat_source_table"] = "bright"
    ordered = [base, bright] if (prefer == "bright") else [bright, base]
    merged = pd.concat(ordered, ignore_index=True, sort=False)
    duplicate_count = int(merged[source_id_column].duplicated(keep=False).sum())
    merged = merged.drop_duplicates(subset=[source_id_column], keep="last").reset_index(drop=True)

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(destination, index=False)

    payload = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "base_catalog": str(Path(base_catalog).resolve()),
        "bright_catalog": str(Path(bright_catalog).resolve()),
        "output_catalog": str(destination.resolve()),
        "base_sha256": sha256_file(base_catalog),
        "bright_sha256": sha256_file(bright_catalog),
        "source_id_column": source_id_column,
        "prefer": prefer,
        "base_rows": int(len(base)),
        "bright_rows": int(len(bright)),
        "merged_rows": int(len(merged)),
        "duplicate_source_id_rows_before_drop": duplicate_count,
    }
    if (provenance_output is not None):
        atomic_write_json(provenance_output, payload)
        payload["provenance_output"] = str(Path(provenance_output))
    return payload
