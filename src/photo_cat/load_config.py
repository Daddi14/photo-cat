# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Parse, resolve and validate PHOTO-CAT configuration sections."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[2]
ROOT_CONFIG_PATH = PROJECT_DIR / "config.yaml"
BUILD_SECTION = "build_neighbors_index"
QUERY_SECTION = "query_contamination_from_index"
EXECUTION_SECTION = "execution"


@dataclass(frozen=True)
class BuildConfig:
    input_catalog: str
    out_dir: str
    KDTREE_FILENAME: str
    use_dask: bool
    calculate_separations: bool
    max_radius_arcsec: float
    chunk_size: int
    buffer_flush_interval: int
    usecolumns: list[str]
    source_id_column: str
    ra_column: str
    dec_column: str
    phot_g_mean_mag_column: str


@dataclass(frozen=True)
class QueryConfig:
    INDEX_DIR: str
    TARGETS_INPUT: str | None
    field_of_view_arcsec: float
    delta_mag: float
    targets: list[str | int]
    target_source_id_column: str


@dataclass(frozen=True)
class ExecutionConfig:
    run_build: bool
    run_query: bool
    replace_running_pipeline: bool


def resolve_config_path(config_path: str | None = None) -> Path:
    """Resolve an explicit config path, ``PHOTO_CAT_CONFIG``, or the project default."""
    if (config_path is None):
        path_text = os.environ.get("PHOTO_CAT_CONFIG", "").strip() or str(ROOT_CONFIG_PATH)
    else:
        path_text = str(config_path).strip()

    path = Path(os.path.expanduser(path_text))
    if (not path.is_absolute()):
        path = PROJECT_DIR / path

    return path.resolve()


def read_config_file(config_path: Path) -> dict[str, Any]:
    """Read a YAML mapping from ``config_path`` with user-facing errors."""
    if (not config_path.is_file()):
        raise FileNotFoundError(f"config.yaml was not found here: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}

    if (not isinstance(config, dict)):
        raise ValueError(f"config.yaml must contain a YAML mapping at the top level: {config_path}")

    return config


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    """Return a mapping value or explain which configuration path is malformed."""
    if (value is None):
        return {}

    if (not isinstance(value, dict)):
        raise ValueError(f"{label} must be a YAML mapping.")

    return value


def require_text(value: Any, label: str, default: str | None = None) -> str:
    """Return a non-empty text configuration value."""
    if (value is None):
        if (default is None):
            raise ValueError(f"{label} cannot be empty.")
        value = default

    text = str(value).strip()
    if (text == ""):
        raise ValueError(f"{label} cannot be empty.")

    return text


def parse_bool(value: Any, label: str, default: bool) -> bool:
    """Parse a strict boolean while accepting YAML and common CLI text forms."""
    if (value is None):
        return default

    if (isinstance(value, bool)):
        return value

    if (isinstance(value, str)):
        normalized = value.strip().lower()
        if (normalized in {"true", "yes", "1", "on"}):
            return True
        if (normalized in {"false", "no", "0", "off"}):
            return False

    raise ValueError(f"{label} must be true or false.")


def parse_float(
    value: Any,
    label: str,
    default: float,
    *,
    minimum: float | None = None,
    exclusive_minimum: bool = False,
) -> float:
    """Parse a finite numeric setting and optionally enforce a lower bound."""
    if (value is None):
        return default

    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number.") from error

    if (not math.isfinite(result)):
        raise ValueError(f"{label} must be a finite number.")

    if (minimum is not None):
        below_minimum = result <= minimum if (exclusive_minimum) else result < minimum
        if (below_minimum):
            comparison = f"greater than {minimum}" if (exclusive_minimum) else f"at least {minimum}"
            raise ValueError(f"{label} must be {comparison}.")

    return result


def parse_positive_int(value: Any, label: str, default: int) -> int:
    """Parse a positive integer without silently truncating decimal values."""
    if (value is None):
        return default

    if (isinstance(value, bool)):
        raise ValueError(f"{label} must be a positive integer.")

    try:
        numeric_value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a positive integer.") from error

    if (not math.isfinite(numeric_value) or not numeric_value.is_integer()):
        raise ValueError(f"{label} must be a positive integer.")

    result = int(numeric_value)
    if (result <= 0):
        raise ValueError(f"{label} must be a positive integer.")

    return result


def resolve_path(path_value: str | None, config_dir: Path) -> str | None:
    """Resolve a user path relative to the directory containing ``config.yaml``."""
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
    """Return an existing file path or raise a direct user-facing error."""
    if (path_value is None):
        return None

    if (not Path(path_value).is_file()):
        raise FileNotFoundError(
            f"{label} was not found: {path_value}\n"
            "Check config.yaml and use / in paths, even on Windows."
        )

    return path_value


def validate_output_directory(path_value: str, label: str) -> str:
    """Reject output paths that already point to a regular file."""
    output_path = Path(path_value)

    if (output_path.exists() and not output_path.is_dir()):
        raise ValueError(
            f"{label} must be a directory, but it points to an existing file:\n{output_path}\n\n"
            "Choose a new output folder or remove/rename the conflicting file."
        )

    return str(output_path)


def validate_output_filename(value: str, label: str) -> str:
    """Require an output filename rather than a path outside the configured output folder."""
    filename = require_text(value, label)

    if (filename in {".", ".."} or "/" in filename or "\\" in filename):
        raise ValueError(
            f"{label} must be a filename only, not a path: {filename}\n"
            "Use --out-dir/config out_dir to choose the folder."
        )

    return filename


def column_name(columns: dict[str, Any], legacy_usecolumns: list[Any], key: str, index: int, default: str) -> str:
    """Resolve one catalogue column name from the modern mapping, legacy list, or default."""
    if (columns.get(key) is not None):
        return require_text(columns[key], f"build_neighbors_index.io.columns.{key}")

    if (len(legacy_usecolumns) > index and legacy_usecolumns[index] is not None):
        return require_text(legacy_usecolumns[index], f"build_neighbors_index.io.usecolumns[{index}]")

    return default


def validate_columns(columns: list[str]) -> None:
    """Require distinct, non-empty catalogue column names."""
    if (any(column == "" for column in columns)):
        raise ValueError("Catalog column names cannot be empty.")

    if (len(set(columns)) != len(columns)):
        raise ValueError("Catalog source_id, ra, dec, and phot_g_mean_mag columns must be different.")


def load_build_config(section_config: dict[str, Any], config_dir: Path) -> BuildConfig:
    """Create a validated ``BuildConfig`` from the build configuration section."""
    io = require_mapping(section_config.get("io"), f"{BUILD_SECTION}.io")
    settings = require_mapping(section_config.get("settings"), f"{BUILD_SECTION}.settings")

    input_catalog = require_file(resolve_path(io.get("input_catalog"), config_dir), "input_catalog")
    if (input_catalog is None):
        raise ValueError("build_neighbors_index.io.input_catalog cannot be empty.")

    out_dir = resolve_path(io.get("out_dir"), config_dir)
    if (out_dir is None):
        raise ValueError("build_neighbors_index.io.out_dir cannot be empty.")

    columns = require_mapping(io.get("columns"), f"{BUILD_SECTION}.io.columns")
    legacy_usecolumns = io.get("usecolumns") or []
    if (not isinstance(legacy_usecolumns, list)):
        raise ValueError("build_neighbors_index.io.usecolumns must be a list when provided.")

    source_id_column = column_name(columns, legacy_usecolumns, "source_id", 0, "source_id")
    ra_column = column_name(columns, legacy_usecolumns, "ra", 1, "ra")
    dec_column = column_name(columns, legacy_usecolumns, "dec", 2, "dec")
    phot_g_mean_mag_column = column_name(columns, legacy_usecolumns, "phot_g_mean_mag", 3, "phot_g_mean_mag")
    usecolumns = [source_id_column, ra_column, dec_column, phot_g_mean_mag_column]
    validate_columns(usecolumns)

    return BuildConfig(
        input_catalog=input_catalog,
        out_dir=validate_output_directory(out_dir, "build_neighbors_index.io.out_dir"),
        KDTREE_FILENAME=validate_output_filename(
            require_text(io.get("KDTREE_FILENAME"), "build_neighbors_index.io.KDTREE_FILENAME", "ckdtree.pkl"),
            "build_neighbors_index.io.KDTREE_FILENAME",
        ),
        use_dask=parse_bool(settings.get("use_dask"), "build_neighbors_index.settings.use_dask", True),
        calculate_separations=parse_bool(
            settings.get("calculate_separations"),
            "build_neighbors_index.settings.calculate_separations",
            False,
        ),
        max_radius_arcsec=parse_float(
            settings.get("max_radius_arcsec"),
            "build_neighbors_index.settings.max_radius_arcsec",
            120.0,
            minimum=0.0,
            exclusive_minimum=True,
        ),
        chunk_size=parse_positive_int(settings.get("chunk_size"), "build_neighbors_index.settings.chunk_size", 10000),
        buffer_flush_interval=parse_positive_int(
            settings.get("buffer_flush_interval"),
            "build_neighbors_index.settings.buffer_flush_interval",
            200,
        ),
        usecolumns=usecolumns,
        source_id_column=source_id_column,
        ra_column=ra_column,
        dec_column=dec_column,
        phot_g_mean_mag_column=phot_g_mean_mag_column,
    )


def load_query_config(section_config: dict[str, Any], config_dir: Path) -> QueryConfig:
    """Create a validated ``QueryConfig`` from the query configuration section."""
    io = require_mapping(section_config.get("io"), f"{QUERY_SECTION}.io")
    settings = require_mapping(section_config.get("settings"), f"{QUERY_SECTION}.settings")

    index_dir = resolve_path(io.get("INDEX_DIR"), config_dir)
    if (index_dir is None):
        raise ValueError("query_contamination_from_index.io.INDEX_DIR cannot be empty.")

    targets_input = require_file(resolve_path(io.get("TARGETS_INPUT"), config_dir), "TARGETS_INPUT")
    targets = io.get("targets") or []
    if (not isinstance(targets, list)):
        raise ValueError("query_contamination_from_index.io.targets must be a list.")

    target_source_id_column = require_text(
        io.get("target_source_id_column"),
        "query_contamination_from_index.io.target_source_id_column",
        "source_id",
    )

    if (targets_input is None and not targets):
        raise ValueError("No targets were configured. Set TARGETS_INPUT to a CSV file, or set targets to a list.")

    return QueryConfig(
        INDEX_DIR=index_dir,
        TARGETS_INPUT=targets_input,
        field_of_view_arcsec=parse_float(
            settings.get("field_of_view_arcsec"),
            "query_contamination_from_index.settings.field_of_view_arcsec",
            47.0,
            minimum=0.0,
            exclusive_minimum=True,
        ),
        delta_mag=parse_float(
            settings.get("delta_mag"),
            "query_contamination_from_index.settings.delta_mag",
            5.0,
        ),
        targets=targets,
        target_source_id_column=target_source_id_column,
    )


def load_execution_config(section_config: dict[str, Any]) -> ExecutionConfig:
    """Create a validated ``ExecutionConfig`` from the execution section."""
    return ExecutionConfig(
        run_build=parse_bool(section_config.get("run_build"), "execution.run_build", True),
        run_query=parse_bool(section_config.get("run_query"), "execution.run_query", True),
        replace_running_pipeline=parse_bool(
            section_config.get("replace_running_pipeline"),
            "execution.replace_running_pipeline",
            True,
        ),
    )


def load_config(section: str, config_path: str | None = None) -> BuildConfig | QueryConfig | ExecutionConfig:
    """Load a supported configuration section as a validated dataclass."""
    resolved_config_path = resolve_config_path(config_path)
    config = read_config_file(resolved_config_path)

    if (section not in config):
        raise ValueError(f"Unknown configuration section: {section}")

    section_config = require_mapping(config[section], f"Configuration section {section}")
    config_dir = resolved_config_path.parent

    if (section == BUILD_SECTION):
        return load_build_config(section_config, config_dir)

    if (section == QUERY_SECTION):
        return load_query_config(section_config, config_dir)

    if (section == EXECUTION_SECTION):
        return load_execution_config(section_config)

    raise ValueError(f"Unsupported configuration section: {section}")
