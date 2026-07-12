# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Parse, resolve, validate, and isolate PHOTO-CAT configuration state."""

from __future__ import annotations

import copy
import math
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml

from .path_policy import (
    require_existing_file,
    resolve_config_file_path,
    resolve_user_path,
    validate_directory_target,
)


PROJECT_DIR = Path(__file__).resolve().parents[2]
ROOT_CONFIG_PATH = PROJECT_DIR / "config.yaml"
BUILD_SECTION = "build_neighbors_index"
QUERY_SECTION = "query_contamination_from_index"
EXECUTION_SECTION = "execution"


@dataclass(frozen=True)
class BuildConfig:
    """Validated build/index settings with paths resolved against config.yaml."""

    input_catalog: str
    out_dir: str
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
    magnitude_columns: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ContaminationModelConfig:
    """Validated query-side contamination weighting model."""

    mode: str = "top_hat"
    gaussian_fwhm_arcsec: float | None = None
    radial_weight_file: str | None = None


@dataclass(frozen=True)
class QueryConfig:
    """Validated query settings with paths resolved against config.yaml."""

    INDEX_DIR: str
    TARGETS_INPUT: str | None
    field_of_view_arcsec: float
    delta_mag: float
    targets: list[str | int]
    target_source_id_column: str
    include_missing_targets: bool = False
    contamination_model: ContaminationModelConfig = field(default_factory=ContaminationModelConfig)
    contamination_bands: list[str] = field(default_factory=lambda: ["gaia_g"])
    influence_radius_arcsec: float | None = None
    bandpass_transform_file: str | None = None

    @property
    def aperture_radius_arcsec(self) -> float:
        """Return the legacy field-of-view setting using its physical aperture meaning."""
        return self.field_of_view_arcsec

    @property
    def effective_influence_radius_arcsec(self) -> float:
        """Return the outer neighbour radius, defaulting to the aperture for compatibility."""
        return self.field_of_view_arcsec if self.influence_radius_arcsec is None else self.influence_radius_arcsec


@dataclass(frozen=True)
class ExecutionConfig:
    """Pipeline stage-selection settings independent from runtime resources."""

    run_build: bool
    run_query: bool
    replace_running_pipeline: bool


@dataclass(frozen=True)
class ConfigurationDocument:
    """One parsed configuration file and its immutable location context.

    ``data`` is retained only as the source document. Section readers return deep
    copies, so parsing and CLI-derived configuration cannot mutate the original
    loaded YAML mapping or leak state into a later load.
    """

    path: Path
    data: dict[str, Any]

    @property
    def directory(self) -> Path:
        """Return the directory that anchors config-relative paths."""
        return self.path.parent

    def section(self, section: str) -> dict[str, Any]:
        """Return an isolated copy of one supported configuration section."""
        if (section not in self.data):
            raise ValueError(f"Unknown configuration section: {section}")

        return copy.deepcopy(require_mapping(self.data[section], f"Configuration section {section}"))


@dataclass(frozen=True)
class PipelineConfiguration:
    """All independently parsed PHOTO-CAT sections from one configuration file."""

    document: ConfigurationDocument
    build: BuildConfig
    query: QueryConfig
    execution: ExecutionConfig


def resolve_config_path(config_path: str | Path | None = None) -> Path:
    """Resolve explicit, environment, and project-default config locations."""
    return resolve_config_file_path(
        config_path,
        base_dir=PROJECT_DIR,
        default_path=ROOT_CONFIG_PATH,
        environment_path=os.environ.get("PHOTO_CAT_CONFIG"),
    )


def read_config_file(config_path: Path) -> dict[str, Any]:
    """Read a YAML mapping from ``config_path`` without creating runtime resources."""
    if (not config_path.is_file()):
        raise FileNotFoundError(f"config.yaml was not found here: {config_path}")

    try:
        with config_path.open("r", encoding="utf-8") as file:
            config = yaml.safe_load(file) or {}
    except yaml.YAMLError as error:
        raise ValueError(f"config.yaml contains invalid YAML: {config_path}") from error

    if (not isinstance(config, dict)):
        raise ValueError(f"config.yaml must contain a YAML mapping at the top level: {config_path}")

    return config


def load_configuration_document(config_path: str | Path | None = None) -> ConfigurationDocument:
    """Load one YAML document without validating inputs or creating output folders."""
    resolved_path = resolve_config_path(config_path)
    return ConfigurationDocument(resolved_path, read_config_file(resolved_path))


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
    maximum: float | None = None,
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

    if (maximum is not None and result > maximum):
        raise ValueError(f"{label} must be at most {maximum}.")

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
    resolved_path = resolve_user_path(path_value, config_dir)
    return (None if (resolved_path is None) else str(resolved_path))


def resolve_required_path(path_value: str | None, label: str, config_dir: Path) -> str:
    """Resolve a required path without touching the filesystem beyond path normalization."""
    resolved_path = resolve_path(path_value, config_dir)
    if (resolved_path is None):
        raise ValueError(f"{label} cannot be empty.")

    return resolved_path


def require_file(path_value: str | None, label: str) -> str | None:
    """Return an existing file path or raise a direct user-facing error."""
    required_path = require_existing_file((None if (path_value is None) else Path(path_value)), label)
    return (None if (required_path is None) else str(required_path))


def validate_output_directory(path_value: str, label: str) -> str:
    """Reject output paths that already point to a regular file."""
    return str(validate_directory_target(Path(path_value), label))


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


def parse_text_mapping(value: Any, label: str) -> dict[str, str]:
    """Parse a YAML mapping whose keys and values must be non-empty text."""
    if (value is None):
        return {}
    mapping = require_mapping(value, label)
    parsed: dict[str, str] = {}
    for key, item in mapping.items():
        parsed[require_text(key, f"{label} key")] = require_text(item, f"{label}.{key}")
    return parsed


def normalize_magnitude_columns(
    configured_columns: dict[str, str],
    phot_g_mean_mag_column: str,
) -> dict[str, str]:
    """Return a band-to-catalogue-column map with a stable Gaia-G default."""
    magnitude_columns = {"gaia_g": phot_g_mean_mag_column}
    magnitude_columns.update(configured_columns)

    for band in magnitude_columns:
        if (band.strip() == ""):
            raise ValueError("build_neighbors_index.io.magnitude_columns band names cannot be empty.")

    return magnitude_columns


def parse_contamination_model(settings: dict[str, Any], config_dir: Path) -> ContaminationModelConfig:
    """Parse opt-in aperture/PSF-style weighting settings for query flux metrics."""
    raw_model = settings.get("contamination_model")
    if (raw_model is None):
        return ContaminationModelConfig()
    model = require_mapping(raw_model, f"{QUERY_SECTION}.settings.contamination_model")
    mode = require_text(model.get("mode"), f"{QUERY_SECTION}.settings.contamination_model.mode", "top_hat")
    normalized_mode = mode.lower().replace("-", "_")
    if (normalized_mode not in {"top_hat", "radial_weight", "gaussian_psf", "gaussian_aperture"}):
        raise ValueError(
            "query_contamination_from_index.settings.contamination_model.mode "
            "must be one of: top_hat, radial_weight, gaussian_psf, gaussian_aperture."
        )

    gaussian_fwhm_arcsec = None
    if (model.get("gaussian_fwhm_arcsec") is not None):
        gaussian_fwhm_arcsec = parse_float(
            model.get("gaussian_fwhm_arcsec"),
            f"{QUERY_SECTION}.settings.contamination_model.gaussian_fwhm_arcsec",
            0.0,
            minimum=0.0,
            exclusive_minimum=True,
        )

    radial_weight_file = resolve_path(model.get("radial_weight_file"), config_dir)

    if (normalized_mode in {"gaussian_psf", "gaussian_aperture"} and gaussian_fwhm_arcsec is None):
        raise ValueError(
            "query_contamination_from_index.settings.contamination_model.gaussian_fwhm_arcsec "
            "is required when mode is gaussian_psf or gaussian_aperture."
        )
    if (normalized_mode == "radial_weight" and radial_weight_file is None):
        raise ValueError(
            "query_contamination_from_index.settings.contamination_model.radial_weight_file "
            "is required when mode is radial_weight."
        )

    return ContaminationModelConfig(
        mode=normalized_mode,
        gaussian_fwhm_arcsec=gaussian_fwhm_arcsec,
        radial_weight_file=radial_weight_file,
    )


def parse_contamination_bands(settings: dict[str, Any]) -> list[str]:
    """Parse requested result bands while keeping Gaia-G as the default metric."""
    raw_bands = settings.get("contamination_bands")
    if (raw_bands is None):
        return ["gaia_g"]
    if (not isinstance(raw_bands, list)):
        raise ValueError("query_contamination_from_index.settings.contamination_bands must be a list.")
    bands = [require_text(item, "query_contamination_from_index.settings.contamination_bands[]") for item in raw_bands]
    if (not bands):
        raise ValueError("query_contamination_from_index.settings.contamination_bands cannot be empty.")
    return bands


def load_build_config(section_config: dict[str, Any], config_dir: Path) -> BuildConfig:
    """Parse a build config without checking files or creating output directories."""
    io = require_mapping(section_config.get("io"), f"{BUILD_SECTION}.io")
    settings = require_mapping(section_config.get("settings"), f"{BUILD_SECTION}.settings")

    columns = require_mapping(io.get("columns"), f"{BUILD_SECTION}.io.columns")
    legacy_usecolumns = io.get("usecolumns") or []
    if (not isinstance(legacy_usecolumns, list)):
        raise ValueError("build_neighbors_index.io.usecolumns must be a list when provided.")

    source_id_column = column_name(columns, legacy_usecolumns, "source_id", 0, "source_id")
    ra_column = column_name(columns, legacy_usecolumns, "ra", 1, "ra")
    dec_column = column_name(columns, legacy_usecolumns, "dec", 2, "dec")
    phot_g_mean_mag_column = column_name(columns, legacy_usecolumns, "phot_g_mean_mag", 3, "phot_g_mean_mag")
    magnitude_columns = normalize_magnitude_columns(
        parse_text_mapping(io.get("magnitude_columns"), f"{BUILD_SECTION}.io.magnitude_columns"),
        phot_g_mean_mag_column,
    )
    usecolumns = [source_id_column, ra_column, dec_column, phot_g_mean_mag_column]
    validate_columns(usecolumns)

    return BuildConfig(
        input_catalog=resolve_required_path(
            io.get("input_catalog"),
            "build_neighbors_index.io.input_catalog",
            config_dir,
        ),
        out_dir=resolve_required_path(io.get("out_dir"), "build_neighbors_index.io.out_dir", config_dir),
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
            maximum=648000.0,
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
        magnitude_columns=magnitude_columns,
    )


def validate_build_config_runtime(config: BuildConfig) -> BuildConfig:
    """Validate build filesystem inputs after pure parsing has already succeeded."""
    input_catalog = require_file(config.input_catalog, "input_catalog")
    if (input_catalog is None):
        raise RuntimeError("Build input catalog unexpectedly resolved to None.")

    return replace(
        config,
        input_catalog=input_catalog,
        out_dir=validate_output_directory(config.out_dir, "build_neighbors_index.io.out_dir"),
    )


def load_query_config(section_config: dict[str, Any], config_dir: Path) -> QueryConfig:
    """Parse a query config without checking target files or opening an index."""
    io = require_mapping(section_config.get("io"), f"{QUERY_SECTION}.io")
    settings = require_mapping(section_config.get("settings"), f"{QUERY_SECTION}.settings")

    targets_input = resolve_path(io.get("TARGETS_INPUT"), config_dir)
    targets = io.get("targets") or []
    if (not isinstance(targets, list)):
        raise ValueError("query_contamination_from_index.io.targets must be a list.")

    if (targets_input is None and not targets):
        raise ValueError("No targets were configured. Set TARGETS_INPUT to a CSV file, or set targets to a list.")

    aperture_radius_arcsec = parse_float(
        settings.get("field_of_view_arcsec"),
        "query_contamination_from_index.settings.field_of_view_arcsec",
        47.0,
        minimum=0.0,
        exclusive_minimum=True,
        maximum=648000.0,
    )
    influence_radius_arcsec = parse_float(
        settings.get("influence_radius_arcsec"),
        "query_contamination_from_index.settings.influence_radius_arcsec",
        aperture_radius_arcsec,
        minimum=0.0,
        exclusive_minimum=True,
        maximum=648000.0,
    )
    if (influence_radius_arcsec < aperture_radius_arcsec):
        raise ValueError(
            "query_contamination_from_index.settings.influence_radius_arcsec "
            "must be greater than or equal to field_of_view_arcsec."
        )

    return QueryConfig(
        INDEX_DIR=resolve_required_path(io.get("INDEX_DIR"), "query_contamination_from_index.io.INDEX_DIR", config_dir),
        TARGETS_INPUT=targets_input,
        field_of_view_arcsec=aperture_radius_arcsec,
        delta_mag=parse_float(
            settings.get("delta_mag"),
            "query_contamination_from_index.settings.delta_mag",
            5.0,
        ),
        targets=copy.deepcopy(targets),
        target_source_id_column=require_text(
            io.get("target_source_id_column"),
            "query_contamination_from_index.io.target_source_id_column",
            "source_id",
        ),
        include_missing_targets=parse_bool(
            settings.get("include_missing_targets"),
            "query_contamination_from_index.settings.include_missing_targets",
            False,
        ),
        contamination_model=parse_contamination_model(settings, config_dir),
        contamination_bands=parse_contamination_bands(settings),
        influence_radius_arcsec=influence_radius_arcsec,
        bandpass_transform_file=resolve_path(settings.get("bandpass_transform_file"), config_dir),
    )


def validate_query_config_runtime(config: QueryConfig) -> QueryConfig:
    """Validate query target inputs after pure parsing and resolution succeed."""
    targets_input = require_file(config.TARGETS_INPUT, "TARGETS_INPUT")
    radial_weight_file = config.contamination_model.radial_weight_file
    if (radial_weight_file is not None):
        radial_weight_file = require_file(radial_weight_file, "contamination_model.radial_weight_file")
    bandpass_transform_file = require_file(config.bandpass_transform_file, "bandpass_transform_file")
    return replace(
        config,
        TARGETS_INPUT=targets_input,
        contamination_model=replace(config.contamination_model, radial_weight_file=radial_weight_file),
        bandpass_transform_file=bandpass_transform_file,
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


def load_config_from_document(
    section: str,
    document: ConfigurationDocument,
    *,
    validate_runtime: bool = True,
) -> BuildConfig | QueryConfig | ExecutionConfig:
    """Parse one isolated section from a document and optionally validate runtime inputs."""
    section_config = document.section(section)

    if (section == BUILD_SECTION):
        build_config = load_build_config(section_config, document.directory)
        return validate_build_config_runtime(build_config) if validate_runtime else build_config

    if (section == QUERY_SECTION):
        query_config = load_query_config(section_config, document.directory)
        return validate_query_config_runtime(query_config) if validate_runtime else query_config

    if (section == EXECUTION_SECTION):
        return load_execution_config(section_config)

    raise ValueError(f"Unsupported configuration section: {section}")


def load_config(
    section: str,
    config_path: str | Path | None = None,
    *,
    validate_runtime: bool = True,
) -> BuildConfig | QueryConfig | ExecutionConfig:
    """Load one supported section without leaking mutable state across loads."""
    document = load_configuration_document(config_path)
    return load_config_from_document(section, document, validate_runtime=validate_runtime)


def load_pipeline_configuration(
    config_path: str | Path | None = None,
    *,
    validate_runtime: bool = True,
) -> PipelineConfiguration:
    """Parse all supported sections from one YAML document with a shared path context."""
    document = load_configuration_document(config_path)
    build = load_config_from_document(BUILD_SECTION, document, validate_runtime=validate_runtime)
    query = load_config_from_document(QUERY_SECTION, document, validate_runtime=validate_runtime)
    execution = load_config_from_document(EXECUTION_SECTION, document, validate_runtime=validate_runtime)

    if (not isinstance(build, BuildConfig) or not isinstance(query, QueryConfig) or not isinstance(execution, ExecutionConfig)):
        raise RuntimeError("Failed to assemble the PHOTO-CAT pipeline configuration.")

    return PipelineConfiguration(document, build, query, execution)
