# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Runtime configuration overrides used by the PHOTO-CAT CLI."""

from __future__ import annotations

import copy
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "build_neighbors_index": {
        "io": {
            "input_catalog": "data/example_catalog.csv",
            "out_dir": "data/output",
            "KDTREE_FILENAME": "ckdtree.pkl",
            "usecolumns": [
                "source_id",
                "ra",
                "dec",
                "phot_g_mean_mag",
            ],
            "columns": {
                "source_id": "source_id",
                "ra": "ra",
                "dec": "dec",
                "phot_g_mean_mag": "phot_g_mean_mag",
            },
        },
        "settings": {
            "use_dask": True,
            "calculate_separations": False,
            "max_radius_arcsec": 120.0,
            "chunk_size": 10000,
            "buffer_flush_interval": 200,
        },
    },
    "query_contamination_from_index": {
        "io": {
            "INDEX_DIR": "data/output",
            "TARGETS_INPUT": "data/example_targets.csv",
            "targets": [],
            "target_source_id_column": "source_id",
        },
        "settings": {
            "field_of_view_arcsec": 47.0,
            "delta_mag": 5.0,
        },
    },
    "execution": {
        "run_build": True,
        "run_query": True,
        "replace_running_pipeline": True,
    },
}


OVERRIDE_PATHS: dict[str, tuple[str, ...]] = {
    "input_catalog": ("build_neighbors_index", "io", "input_catalog"),
    "out_dir": ("build_neighbors_index", "io", "out_dir"),
    "kdtree_filename": ("build_neighbors_index", "io", "KDTREE_FILENAME"),
    "usecolumns": ("build_neighbors_index", "io", "usecolumns"),
    "catalog_source_id_column": ("build_neighbors_index", "io", "columns", "source_id"),
    "ra_column": ("build_neighbors_index", "io", "columns", "ra"),
    "dec_column": ("build_neighbors_index", "io", "columns", "dec"),
    "phot_g_mean_mag_column": ("build_neighbors_index", "io", "columns", "phot_g_mean_mag"),
    "use_dask": ("build_neighbors_index", "settings", "use_dask"),
    "calculate_separations": ("build_neighbors_index", "settings", "calculate_separations"),
    "max_radius_arcsec": ("build_neighbors_index", "settings", "max_radius_arcsec"),
    "chunk_size": ("build_neighbors_index", "settings", "chunk_size"),
    "buffer_flush_interval": ("build_neighbors_index", "settings", "buffer_flush_interval"),
    "index_dir": ("query_contamination_from_index", "io", "INDEX_DIR"),
    "targets_input": ("query_contamination_from_index", "io", "TARGETS_INPUT"),
    "targets": ("query_contamination_from_index", "io", "targets"),
    "target_source_id_column": ("query_contamination_from_index", "io", "target_source_id_column"),
    "field_of_view_arcsec": ("query_contamination_from_index", "settings", "field_of_view_arcsec"),
    "delta_mag": ("query_contamination_from_index", "settings", "delta_mag"),
    "run_build": ("execution", "run_build"),
    "run_query": ("execution", "run_query"),
    "replace_running_pipeline": ("execution", "replace_running_pipeline"),
}


PATH_OVERRIDE_NAMES = {
    "input_catalog",
    "out_dir",
    "index_dir",
    "targets_input",
}


def load_base_config(config_path: Path | None) -> tuple[dict[str, Any], Path]:
    """Load a base config and return the config plus the directory used for relative paths."""
    if (config_path is not None and config_path.is_file()):
        with config_path.open("r", encoding="utf-8") as f:
            loaded_config = (yaml.safe_load(f) or {})

        if (not isinstance(loaded_config, dict)):
            raise ValueError(f"Configuration file must contain a YAML mapping: {config_path}")

        return loaded_config, config_path.parent.resolve()

    return copy.deepcopy(DEFAULT_CONFIG), Path.cwd().resolve()


def ensure_mapping(config: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    current: dict[str, Any] = config

    for key in keys:
        value = current.get(key)
        if (not isinstance(value, dict)):
            value = {}
            current[key] = value
        current = value

    return current


def set_nested_value(config: dict[str, Any], keys: tuple[str, ...], value: Any) -> None:
    parent = ensure_mapping(config, keys[:-1])
    parent[keys[-1]] = value


def resolve_cli_path(value: str | None) -> str | None:
    """Resolve CLI path override values relative to the current working directory."""
    if (value is None):
        return None

    path_text = str(value).strip()
    if (path_text == ""):
        return None

    path = Path(os.path.expanduser(path_text))
    if (not path.is_absolute()):
        path = Path.cwd() / path

    return str(path.resolve())


def parse_csv_list(value: str | None) -> list[str]:
    if (value is None):
        return []

    return [item.strip() for item in str(value).split(",") if (item.strip() != "")]


def parse_targets(value: str | None) -> list[str]:
    return parse_csv_list(value)


def collect_overrides(args: Any) -> dict[str, Any]:
    """Collect non-empty override values from parsed CLI arguments."""
    overrides: dict[str, Any] = {}

    for name in OVERRIDE_PATHS:
        if (not hasattr(args, name)):
            continue

        value = getattr(args, name)
        if (value is None):
            continue

        if (name == "usecolumns"):
            value = parse_csv_list(value)
        elif (name == "targets"):
            value = parse_targets(value)
        elif (name in PATH_OVERRIDE_NAMES):
            value = resolve_cli_path(value)

        overrides[name] = value

    if (getattr(args, "no_targets_input", False)):
        overrides["targets_input"] = None

    return overrides


def apply_overrides(config: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of config with CLI overrides applied."""
    updated = copy.deepcopy(config)

    for name, value in overrides.items():
        if (name not in OVERRIDE_PATHS):
            raise ValueError(f"Unsupported CLI override: {name}")
        set_nested_value(updated, OVERRIDE_PATHS[name], value)

    if ("catalog_source_id_column" in overrides):
        source_id_column = overrides["catalog_source_id_column"]
        set_nested_value(updated, ("build_neighbors_index", "io", "usecolumns"), [
            source_id_column,
            updated["build_neighbors_index"]["io"]["columns"]["ra"],
            updated["build_neighbors_index"]["io"]["columns"]["dec"],
            updated["build_neighbors_index"]["io"]["columns"]["phot_g_mean_mag"],
        ])

    if ("ra_column" in overrides or "dec_column" in overrides or "phot_g_mean_mag_column" in overrides):
        columns = updated["build_neighbors_index"]["io"]["columns"]
        set_nested_value(updated, ("build_neighbors_index", "io", "usecolumns"), [
            columns["source_id"],
            columns["ra"],
            columns["dec"],
            columns["phot_g_mean_mag"],
        ])

    return updated


class RuntimeConfigOverride:
    """Context manager that writes a temporary config when CLI overrides are used."""

    def __init__(self, config_path: Path | None, overrides: dict[str, Any]):
        self.config_path = config_path
        self.overrides = overrides
        self.runtime_config_path: Path | None = None
        self.previous_config_environment: str | None = None

    def __enter__(self) -> Path | None:
        if (not self.overrides):
            if (self.config_path is not None):
                os.environ["PHOTO_CAT_CONFIG"] = str(self.config_path)
            return self.config_path

        base_config, base_dir = load_base_config(self.config_path)
        runtime_config = apply_overrides(base_config, self.overrides)

        temp_name = f".photo-cat-cli-{os.getpid()}-{uuid.uuid4().hex}.yaml"
        temp_dir = base_dir if base_dir.is_dir() else Path(tempfile.gettempdir())
        self.runtime_config_path = temp_dir / temp_name

        with self.runtime_config_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(runtime_config, f, sort_keys=False, allow_unicode=True)

        self.previous_config_environment = os.environ.get("PHOTO_CAT_CONFIG")
        os.environ["PHOTO_CAT_CONFIG"] = str(self.runtime_config_path)
        return self.runtime_config_path

    def __exit__(self, exc_type, exc, traceback) -> None:
        if (self.previous_config_environment is None):
            os.environ.pop("PHOTO_CAT_CONFIG", None)
        else:
            os.environ["PHOTO_CAT_CONFIG"] = self.previous_config_environment

        if (self.runtime_config_path is not None):
            try:
                self.runtime_config_path.unlink()
            except FileNotFoundError:
                pass
