# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Load and validate PHOTO-CAT configuration sections."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[2]
ROOT_CONFIG_PATH = PROJECT_DIR / "config.yaml"
BUILD_SECTION = "build_neighbors_index"
QUERY_SECTION = "query_contamination_from_index"


@dataclass
class BuildConfig:
    input_catalog: str
    out_dir: str
    KDTREE_FILENAME: str
    use_dask: bool
    calculate_separations: bool
    max_radius_arcsec: float
    chunk_size: int
    buffer_flush_interval: int
    usecolumns: list
    source_id_column: str
    ra_column: str
    dec_column: str
    phot_g_mean_mag_column: str


@dataclass
class QueryConfig:
    INDEX_DIR: str
    TARGETS_INPUT: str | None
    field_of_view_arcsec: float
    delta_mag: float
    targets: list
    target_source_id_column: str


def resolve_config_path(config_path: str | None = None) -> Path:
    """Resolve the config path from an explicit value, PHOTO_CAT_CONFIG, or the project default."""
    if (config_path is None):
        path_text = os.environ.get("PHOTO_CAT_CONFIG", "").strip() or str(ROOT_CONFIG_PATH)
    else:
        path_text = str(config_path).strip()

    path = Path(os.path.expanduser(path_text))
    if (not path.is_absolute()):
        path = PROJECT_DIR / path

    return path.resolve()


def read_config_file(config_path: Path) -> dict[str, Any]:
    """Read a YAML configuration file and return an empty dict for an empty file."""
    if (not config_path.is_file()):
        raise FileNotFoundError(f"config.yaml was not found here: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = (yaml.safe_load(f) or {})

    if (not isinstance(config, dict)):
        raise ValueError(f"config.yaml must contain a YAML mapping at the top level: {config_path}")

    return config


def resolve_path(path_value: str | None, config_dir: Path) -> str | None:
    """Resolve a user path relative to the directory containing config.yaml."""
    if (path_value is None):
        return None

    path_text = str(path_value).strip()
    if (path_text == ""):
        return None

    path = Path(os.path.expanduser(path_text))
    if (not path.is_absolute()):
        path = config_dir / path

    return str(path.resolve())


def require_file(path_value: str | None, label: str) -> str | None:
    """Return a file path if present, otherwise raise a user-facing error."""
    if (path_value is None):
        return None

    if (not Path(path_value).is_file()):
        raise FileNotFoundError(
            f"{label} was not found: {path_value}\n"
            "Check config.yaml and use / in paths, even on Windows."
        )

    return path_value


def column_name(columns: dict[str, Any], legacy_usecolumns: list, key: str, index: int, default: str) -> str:
    """Resolve one catalog column name from the modern mapping, legacy list, or default."""
    if (columns.get(key)):
        return str(columns[key]).strip()

    if (len(legacy_usecolumns) > index and legacy_usecolumns[index]):
        return str(legacy_usecolumns[index]).strip()

    return default


def load_build_config(section_config: dict[str, Any], config_dir: Path) -> BuildConfig:
    """Create a validated BuildConfig from the build_neighbors_index section."""
    io = section_config.get("io", {}) or {}
    settings = section_config.get("settings", {}) or {}

    input_catalog = require_file(resolve_path(io.get("input_catalog"), config_dir), "input_catalog")
    out_dir = resolve_path(io.get("out_dir"), config_dir)
    if (out_dir is None):
        raise ValueError("build_neighbors_index.io.out_dir cannot be empty.")

    columns = io.get("columns", {}) or {}
    legacy_usecolumns = io.get("usecolumns", []) or []

    source_id_column = column_name(columns, legacy_usecolumns, "source_id", 0, "source_id")
    ra_column = column_name(columns, legacy_usecolumns, "ra", 1, "ra")
    dec_column = column_name(columns, legacy_usecolumns, "dec", 2, "dec")
    phot_g_mean_mag_column = column_name(columns, legacy_usecolumns, "phot_g_mean_mag", 3, "phot_g_mean_mag")

    usecolumns = [source_id_column, ra_column, dec_column, phot_g_mean_mag_column]
    if (any(column == "" for column in usecolumns)):
        raise ValueError("Catalog column names cannot be empty.")

    if (len(set(usecolumns)) != len(usecolumns)):
        raise ValueError("Catalog source_id, ra, dec, and phot_g_mean_mag columns must be different.")

    return BuildConfig(
        input_catalog=input_catalog,
        out_dir=out_dir,
        KDTREE_FILENAME=str(io.get("KDTREE_FILENAME", "ckdtree.pkl") or "ckdtree.pkl"),
        use_dask=bool(settings.get("use_dask", True)),
        calculate_separations=bool(settings.get("calculate_separations", False)),
        max_radius_arcsec=float(settings.get("max_radius_arcsec", 120.0)),
        chunk_size=int(settings.get("chunk_size", 10000)),
        buffer_flush_interval=int(settings.get("buffer_flush_interval", 200)),
        usecolumns=usecolumns,
        source_id_column=source_id_column,
        ra_column=ra_column,
        dec_column=dec_column,
        phot_g_mean_mag_column=phot_g_mean_mag_column,
    )


def load_query_config(section_config: dict[str, Any], config_dir: Path) -> QueryConfig:
    """Create a validated QueryConfig from the query_contamination_from_index section."""
    io = section_config.get("io", {}) or {}
    settings = section_config.get("settings", {}) or {}

    index_dir = resolve_path(io.get("INDEX_DIR"), config_dir)
    if (index_dir is None):
        raise ValueError("query_contamination_from_index.io.INDEX_DIR cannot be empty.")

    targets_input = require_file(resolve_path(io.get("TARGETS_INPUT"), config_dir), "TARGETS_INPUT")
    targets = io.get("targets", []) or []
    target_source_id_column = str(io.get("target_source_id_column", "source_id") or "source_id").strip()
    if (target_source_id_column == ""):
        raise ValueError("query_contamination_from_index.io.target_source_id_column cannot be empty.")

    if (targets_input is None and not targets):
        raise ValueError(
            "No targets were configured. Set TARGETS_INPUT to a CSV file, or set targets to a list."
        )

    return QueryConfig(
        INDEX_DIR=index_dir,
        TARGETS_INPUT=targets_input,
        field_of_view_arcsec=float(settings.get("field_of_view_arcsec", 47.0)),
        delta_mag=float(settings.get("delta_mag", 5)),
        targets=targets,
        target_source_id_column=target_source_id_column,
    )


def load_config(section: str, config_path: str | None = None):
    """
    Load one section from config.yaml and return it as a dataclass.

    section must be:
      - build_neighbors_index
      - query_contamination_from_index
    """
    resolved_config_path = resolve_config_path(config_path)
    config = read_config_file(resolved_config_path)

    if (section not in config):
        raise ValueError(f"Unknown configuration section: {section}")

    section_config = config[section] or {}
    if (not isinstance(section_config, dict)):
        raise ValueError(f"Configuration section must be a mapping: {section}")

    config_dir = resolved_config_path.parent

    if (section == BUILD_SECTION):
        return load_build_config(section_config, config_dir)

    if (section == QUERY_SECTION):
        return load_query_config(section_config, config_dir)

    raise ValueError(f"Unsupported configuration section: {section}")
