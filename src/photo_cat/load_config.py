# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Load and validate PHOTO-CAT configuration sections."""

import os
from pathlib import Path

import yaml
from dataclasses import dataclass


PROJECT_DIR = Path(__file__).resolve().parents[2]
ROOT_CONFIG_PATH = PROJECT_DIR / "config.yaml"
ENV_CONFIG_PATH = os.environ.get("PHOTO_CAT_CONFIG", "").strip()


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


def load_config(section: str, config_path: str | None = None):
    """
    Load one section from config.yaml and return it as a dataclass.

    section must be:
      - build_neighbors_index
      - query_contamination_from_index
    """
    if (config_path is None):
        config_path = (ENV_CONFIG_PATH or str(ROOT_CONFIG_PATH))
    else:
        config_path = os.path.expanduser(str(config_path))
        if (not os.path.isabs(config_path)):
            config_path = str(PROJECT_DIR / config_path)

    config_path = os.path.abspath(config_path)
    config_dir = os.path.dirname(config_path)

    if (not os.path.isfile(config_path)):
        raise FileNotFoundError(f"config.yaml was not found here: {config_path}")

    def resolve_path(path_value: str | None) -> str | None:
        if (path_value is None):
            return None

        path_value = str(path_value).strip()
        if (path_value == ""):
            return None

        path_value = os.path.expanduser(path_value)
        if (os.path.isabs(path_value)):
            return os.path.normpath(path_value)

        return os.path.normpath(os.path.join(config_dir, path_value))

    def require_file(path_value: str | None, label: str) -> str | None:
        if (path_value is None):
            return None

        if (not os.path.isfile(path_value)):
            raise FileNotFoundError(
                f"{label} was not found: {path_value}\n"
                "Check config.yaml and use / in paths, even on Windows."
            )

        return path_value

    with open(config_path, "r", encoding="utf-8") as f:
        config = (yaml.safe_load(f) or {})

    if (section not in config):
        raise ValueError(f"Unknown configuration section: {section}")

    cfg = config[section]

    if (section == "build_neighbors_index"):
        io = cfg.get("io", {})
        settings = cfg.get("settings", {})

        input_catalog = require_file(resolve_path(io.get("input_catalog")), "input_catalog")
        out_dir = resolve_path(io.get("out_dir"))
        if (out_dir is None):
            raise ValueError("build_neighbors_index.io.out_dir cannot be empty.")

        columns = io.get("columns", {}) or {}
        legacy_usecolumns = io.get("usecolumns", []) or []

        source_id_column = str(columns.get("source_id") or (legacy_usecolumns[0] if len(legacy_usecolumns) > 0 else "source_id")).strip()
        ra_column = str(columns.get("ra") or (legacy_usecolumns[1] if len(legacy_usecolumns) > 1 else "ra")).strip()
        dec_column = str(columns.get("dec") or (legacy_usecolumns[2] if len(legacy_usecolumns) > 2 else "dec")).strip()
        phot_g_mean_mag_column = str(columns.get("phot_g_mean_mag") or (legacy_usecolumns[3] if len(legacy_usecolumns) > 3 else "phot_g_mean_mag")).strip()

        usecolumns = [source_id_column, ra_column, dec_column, phot_g_mean_mag_column]
        if (any(column == "" for column in usecolumns)):
            raise ValueError("Catalog column names cannot be empty.")

        if (len(set(usecolumns)) != len(usecolumns)):
            raise ValueError("Catalog source_id, ra, dec, and phot_g_mean_mag columns must be different.")

        return BuildConfig(
            input_catalog=input_catalog,
            out_dir=out_dir,
            KDTREE_FILENAME=io.get("KDTREE_FILENAME", "ckdtree.pkl"),
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

    if (section == "query_contamination_from_index"):
        io = cfg.get("io", {})
        settings = cfg.get("settings", {})

        index_dir = resolve_path(io.get("INDEX_DIR"))
        if (index_dir is None):
            raise ValueError("query_contamination_from_index.io.INDEX_DIR cannot be empty.")

        targets_input = require_file(resolve_path(io.get("TARGETS_INPUT")), "TARGETS_INPUT")
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

    raise ValueError(f"Unsupported configuration section: {section}")
