#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""
query_contamination_from_index.py

Purpose
-------
Consume the CSR-like neighbor index built by build_neighbors_index.py and
compute contamination metrics for a list of target stars.

Model scope
-----------
PHOTO-CAT's current query model is catalogue-level and aperture-like: it selects
neighbouring catalogue sources inside a configured circular angular radius and
estimates flux ratios from the configured catalogue magnitude column. It does
not perform instrumental PSF convolution, detector-pixel modelling, aperture
weighting, or wavelength-dependent transformations between catalogue and mission
bandpasses. Treat the result as a contamination risk-assessment / target-
screening metric unless a downstream analysis adds mission-specific modelling.

Index files (produced by build_neighbors_index.py)
--------------------------------------------------
    - offsets.npy
        int64 (N+1,), CSR offsets. Neighbors for row i are in:
            neighbors_ids[offsets[i] : offsets[i+1]]

    - neighbors_ids.bin
        int64, binary file of length 'total_neighbors'.
        Contains internal_ids of neighbors, concatenated.

    - ra.npy, dec.npy, phot_g_mean_mag.npy
        float64 arrays of length N. Geometric and photometric columns in
        catalog order (aligned to internal_id = 1..N via index = internal_id - 1).

    - real_ids_int.npy
        int64 array of length N.
        Numeric external IDs (e.g. Gaia source_id), or -1 for rows that have
        non-numeric IDs.

    - special_ids.npz
        Contains:
            * internal_ids : int64[:] -> internal_ids for non-numeric IDs
            * names    : unicode[:] -> original string IDs (e.g. "HD 216608A")

    - master_catalog.parquet
        Full catalog for inspection (not used in this low-memory query path).

Core outputs per target
-----------------------
For each target source_id (real external ID, numeric or string):

    - source_id            : real ID used as input
    - ra, dec              : coordinates of the target
    - phot_g_mean_mag      : G magnitude of the target
    - flux_fraction_selected      : percentage of extra flux from neighbours
                                    inside the circular query radius that also
                                    pass the delta-magnitude cut
    - flux_fraction_all_neighbors : percentage of extra flux from every
                                    neighbour inside the circular query radius,
                                    independent of delta-magnitude cut
    - flux_fraction_extra         : backward-compatible alias of
                                    flux_fraction_selected
    - num_neighbors_in_radius     : number of valid neighbours inside the
                                    circular query radius
    - num_contaminants            : number of neighbours that satisfy radius +
                                    delta-magnitude cut
    - contaminants         : list of Contaminant objects, each with:
                                * source_id
                                * ra, dec
                                * phot_g_mean_mag
                                * sep_arcsec

Inputs (from config_and_run_new)
--------------------------------
    - INDEX_DIR (str)
        Directory containing the index files and arrays.

    - TARGETS_INPUT (str | None)
        CSV path with the configured target source_id column. If None, 'targets' from the config
        is used instead.

    - field_of_view_arcsec (float)
        Circular angular query radius (in arcsec) used as the screening aperture.

    - delta_mag (float)
        Magnitude difference threshold. A contaminant is selected if:
            mag_contaminant - mag_target <= delta_mag

    - n_max_contaminant (int)
        (If you later want to limit the number of stored contaminants per
        target, you can use this parameter; currently the script stores all.)

    - targets (list[int | str] | None)
        Explicit list of real source IDs (numeric or string) if no CSV is used.

Implementation notes
--------------------
    - Uses NumPy memmap for neighbors_ids.bin and the column arrays to avoid
      loading them fully into RAM.
    - Uses a compact ID mapping:
        * numeric IDs via real_ids_int.npy (array indexed by internal_id-1)
        * special string IDs via special_ids.npz (a tiny dictionary).
    - Recomputes angular separations between target and neighbors using the
      Haversine formula on the sphere, then converts to arcsec.
    - Flux is computed via Pogson’s law: F ∝ 10^(-0.4 * mag).

Output
------
    - One target-result JSON file, saved under:
          INDEX_DIR / "output" / "<basename>_FoV..._dmag..._YYYYMMDD_HHMMSS_microseconds.json"
    - One reproducibility metadata sidecar, saved under:
          INDEX_DIR / "output" / "metadata" / "<result_stem>_metadata.json"
"""

import csv
import os
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict

import numpy as np
import pandas as pd

from . import __version__
from .index_manifest import (
    IndexManifest,
    atomic_write_json,
    load_index_manifest,
    validate_index_structure,
)
from .target_result import TargetResult
from .contaminant import Contaminant
from .logger_setup import get_logger
from .load_config import QueryConfig, load_config
from .pipeline_display import ActivityBar, progress_bar
from .path_policy import (
    IndexPaths,
    ensure_query_output_directory,
    index_paths,
    query_output_json_path,
    validate_index_paths,
)


logger = get_logger(__name__)


def read_csv_header(csv_path: str) -> list[str]:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"Targets CSV is empty: {csv_path}")

    return [str(column).strip() for column in header]


def validate_target_column(csv_path: str, target_source_id_column: str) -> None:
    header = read_csv_header(csv_path)

    if (target_source_id_column in header):
        return

    case_matches = [column for column in header if (column.lower() == target_source_id_column.lower())]

    message = (
        "Targets CSV column mismatch.\n\n"
        f"The configured target column was not found: {target_source_id_column}\n"
        "Column names are case-sensitive: source_id is different from Source_ID.\n\n"
    )

    if (case_matches):
        message += (
            "Possible uppercase/lowercase mismatch found:\n"
            + "\n".join(f'- configured "{target_source_id_column}", CSV has "{match}"' for match in case_matches)
            + "\n\n"
        )

    message += (
        f"CSV file:\n{csv_path}\n\n"
        "Available CSV header columns:\n"
        + "\n".join(f"- {column}" for column in header[:80])
    )

    if (len(header) > 80):
        message += f"\n- ... and {len(header) - 80} more"

    raise ValueError(message)




@dataclass(frozen=True)
class QueryRuntimePlan:
    """Validated query paths and output location prepared before numerical work begins."""

    config: QueryConfig
    paths: IndexPaths
    manifest: IndexManifest
    output_json: Path


@dataclass(frozen=True)
class TargetRequest:
    """One requested target, preserving unresolved IDs when requested."""

    source_id: str
    internal_id: int | None
    status: str


def validate_index_directory(index_dir: str) -> IndexPaths:
    """Validate an index directory and return its named runtime paths."""
    return validate_index_paths(index_paths(index_dir))


def prepare_query_runtime(config: QueryConfig) -> QueryRuntimePlan:
    """Validate query filesystem inputs before opening arrays or memory maps."""
    paths = validate_index_directory(config.INDEX_DIR)
    manifest = load_index_manifest(paths.manifest)
    validate_index_structure(paths, manifest)
    if (config.field_of_view_arcsec > manifest.max_radius_arcsec):
        raise ValueError(
            f"Query field_of_view_arcsec ({config.field_of_view_arcsec}) exceeds the index build "
            f"radius ({manifest.max_radius_arcsec}). Rebuild with a larger max_radius_arcsec "
            "or reduce the query aperture radius."
        )
    output_json = query_output_json_path(
        paths,
        config.TARGETS_INPUT,
        config.field_of_view_arcsec,
        config.delta_mag,
    )
    return QueryRuntimePlan(config, paths, manifest, output_json)


def ensure_result_output_directory(index_dir: str) -> Path:
    """Create the query-result folder or report a direct path conflict."""
    return ensure_query_output_directory(index_paths(index_dir))


def create_output_json_path(
    TARGETS_INPUT: Optional[str],
    INDEX_DIR: str,
    field_of_view_arcsec: float,
    delta_mag: float,
) -> str:
    """Build a timestamped JSON result path under the controlled index output directory."""
    return str(
        query_output_json_path(
            index_paths(INDEX_DIR),
            TARGETS_INPUT,
            field_of_view_arcsec,
            delta_mag,
        )
    )


def find_numeric_internal_id(
    numeric_real_ids_sorted: np.ndarray,
    numeric_internal_ids_sorted: np.ndarray,
    real_id: int,
) -> int | None:
    """Return the internal ID for a numeric source ID using binary search."""
    position = np.searchsorted(numeric_real_ids_sorted, real_id)
    if (position < numeric_real_ids_sorted.size and numeric_real_ids_sorted[position] == real_id):
        return int(numeric_internal_ids_sorted[position])

    return None


def resolve_target_internal_ids(
    targets_real: list[str],
    name_to_internal_special: Dict[str, int],
    numeric_real_ids_sorted: np.ndarray,
    numeric_internal_ids_sorted: np.ndarray,
) -> tuple[list[int], list[str], list[str]]:
    """Resolve configured public IDs into internal IDs and classify rejected values."""
    targets_internal: list[int] = []
    invalid_targets: list[str] = []
    missing_targets: list[str] = []

    for target_id in targets_real:
        if (target_id in name_to_internal_special):
            targets_internal.append(name_to_internal_special[target_id])
            continue

        try:
            numeric_target_id = int(target_id)
        except (ValueError, TypeError):
            invalid_targets.append(str(target_id))
            continue

        internal_id = find_numeric_internal_id(
            numeric_real_ids_sorted,
            numeric_internal_ids_sorted,
            numeric_target_id,
        )
        if (internal_id is None):
            missing_targets.append(str(target_id))
        else:
            targets_internal.append(internal_id)

    return targets_internal, invalid_targets, missing_targets


def resolve_target_requests(
    targets_real: list[str],
    name_to_internal_special: Dict[str, int],
    numeric_real_ids_sorted: np.ndarray,
    numeric_internal_ids_sorted: np.ndarray,
) -> list[TargetRequest]:
    """Resolve public target IDs while preserving invalid/missing rows."""
    requests: list[TargetRequest] = []

    for target_id in targets_real:
        target_text = str(target_id)
        if (target_text in name_to_internal_special):
            requests.append(TargetRequest(target_text, name_to_internal_special[target_text], "found"))
            continue

        try:
            numeric_target_id = int(target_text)
        except (ValueError, TypeError):
            requests.append(TargetRequest(target_text, None, "invalid_target_id"))
            continue

        internal_id = find_numeric_internal_id(
            numeric_real_ids_sorted,
            numeric_internal_ids_sorted,
            numeric_target_id,
        )
        if (internal_id is None):
            requests.append(TargetRequest(target_text, None, "missing_from_index"))
        else:
            requests.append(TargetRequest(target_text, internal_id, "found"))

    return requests


def target_id_preview(values: list[str]) -> str:
    """Format a short deterministic preview for target-ID errors and warnings."""
    preview = ", ".join(values[:8])
    suffix = "" if (len(values) <= 8) else f", ... (+{len(values) - 8} more)"
    return preview + suffix


# --- Load catalog and targets (low-memory path) --------------------------------
def load_catalog_arrays(
    INDEX_DIR: str | IndexPaths,
    TARGETS_INPUT: Optional[str] = None,
    targets: Optional[list] = None,
    target_source_id_column: str = "source_id",
    return_target_requests: bool = False,
):
    """
    Low-memory loader for index arrays and target IDs.

    This function:
        - loads RA, Dec, and G magnitude as memory-mapped NumPy arrays
        - loads numeric real IDs from real_ids_int.npy
        - loads special string IDs from special_ids.npz
        - resolves a list of real target IDs (numeric or string) to internal_ids.

    Parameters
    ----------
    INDEX_DIR : str or IndexPaths
        Index root or resolved runtime paths with ra.npy, dec.npy, phot_g_mean_mag.npy,
        real_ids_int.npy and special_ids.npz.

    TARGETS_INPUT : str or None
        Optional CSV path with the configured target source_id column.

    targets : list or None
        Optional in-memory list of source IDs (used if TARGETS_INPUT is None).

    Returns
    -------
    ra : numpy.memmap
        float64, shape (N,). RA in degrees, indexed by (internal_id - 1).

    dec : numpy.memmap
        float64, shape (N,). Dec in degrees, indexed by (internal_id - 1).

    gmag : numpy.memmap or None
        float64, shape (N,) if phot_g_mean_mag.npy exists; otherwise None.

    real_ids_int : numpy.memmap
        int64, shape (N,). Numeric real IDs, or -1 for non-numeric ones.

    internal_to_special_name : dict[int, str]
        Mapping from internal_id to special string source_id (for non-numeric IDs).

    targets_internal : list[int]
        List of internal_ids corresponding to the requested target source_ids.
        Any targets that cannot be matched are skipped (with a warning).
    """
    # Path resolution happens before numerical execution so this function only opens named files.
    paths = INDEX_DIR if isinstance(INDEX_DIR, IndexPaths) else index_paths(INDEX_DIR)

    # Numeric columns as memmap (do not load fully into RAM).
    ra = np.load(paths.ra, mmap_mode="r")
    dec = np.load(paths.dec, mmap_mode="r")

    gmag = None
    gmag_path = paths.phot_g_mean_mag
    if os.path.exists(gmag_path):
        gmag = np.load(gmag_path, mmap_mode="r")

    n_sources = ra.shape[0]
    logger.info(f"Loaded coordinates arrays for {n_sources:,} sources from index.")

    # Numeric real IDs: one per row, -1 where IDs are non-numeric.
    real_ids_int_path = paths.real_ids_int
    real_ids_int = np.load(real_ids_int_path, mmap_mode="r")

    # Special IDs: few rows with non-numeric names (e.g. "HD 216608A").
    special_ids_path = paths.special_ids
    try:
        with np.load(special_ids_path, allow_pickle=False) as special:
            special_internal_ids = special["internal_ids"].astype(np.int64)
            special_names = special["names"].astype(str)
    except ValueError as error:
        raise ValueError(
            "special_ids.npz uses the legacy unsafe object format. Rebuild the index."
        ) from error

    # Mapping internal_id -> special string ID.
    internal_to_special_name: Dict[int, str] = {
        int(f): name for f, name in zip(special_internal_ids, special_names)
    }
    # Mapping string ID -> internal_id for quick lookup when resolving targets.
    name_to_internal_special: Dict[str, int] = {
        name: int(f) for f, name in zip(special_internal_ids, special_names)
    }

    # ------------------------------------------------------------------
    # Build mapping "numeric real_id -> internal_id" using only integers.
    # ------------------------------------------------------------------
    numeric_real_ids_sorted = np.load(
        paths.numeric_real_ids_sorted,
        mmap_mode="r",
        allow_pickle=False,
    )
    numeric_internal_ids_sorted = np.load(
        paths.numeric_internal_ids_sorted,
        mmap_mode="r",
        allow_pickle=False,
    )

    logger.info(f"Prepared numeric mapping for {numeric_real_ids_sorted.size:,} real IDs.")

    # --- Load target list (real IDs as strings) ---
    if TARGETS_INPUT is not None:
        validate_target_column(TARGETS_INPUT, target_source_id_column)
        target_dataframe = pd.read_csv(TARGETS_INPUT, usecols=[target_source_id_column])
        if (len(target_dataframe) == 0):
            raise ValueError(
                "Targets CSV was read successfully, but it contains no data rows.\n"
                "Add at least one target source_id row, or use Manual targets in the GUI."
            )
        targets_real = target_dataframe[target_source_id_column].dropna().astype(str).tolist()
    elif targets is not None:
        targets_real = [str(t) for t in targets if (str(t).strip() != "")]
    else:
        raise ValueError("No targets provided. Set TARGETS_INPUT path or the 'targets' list in the config.")

    if (not targets_real):
        raise ValueError(
            "No valid targets were found.\n\n"
            "Use a Targets CSV with at least one configured Source ID value, or add source_id values under Manual targets in the GUI."
        )

    target_requests = resolve_target_requests(
        targets_real,
        name_to_internal_special,
        numeric_real_ids_sorted,
        numeric_internal_ids_sorted,
    )
    targets_internal = [request.internal_id for request in target_requests if request.internal_id is not None]
    invalid_targets = [request.source_id for request in target_requests if request.status == "invalid_target_id"]
    missing_targets = [request.source_id for request in target_requests if request.status == "missing_from_index"]

    if (invalid_targets):
        logger.warning(
            "Skipped %d target value(s) because they were neither numeric source_id values nor recognised special IDs. Examples: %s",
            len(invalid_targets),
            target_id_preview(invalid_targets),
        )

    if (missing_targets):
        logger.warning(
            "Skipped %d target value(s) because they were not found in the built index. Examples: %s",
            len(missing_targets),
            target_id_preview(missing_targets),
        )

    logger.info("Loaded %d target(s) for analysis.", len(targets_internal))

    if (not targets_internal and not return_target_requests):
        details: list[str] = []
        if (invalid_targets):
            details.append(f"Unrecognised target values: {target_id_preview(invalid_targets)}")
        if (missing_targets):
            details.append(f"Target values not found in the index: {target_id_preview(missing_targets)}")

        raise ValueError(
            "None of the configured targets were found in the built index.\n\n"
            + "\n".join(details)
            + "\n\nMake sure Targets CSV/source_id values come from the same catalog used to build the index."
        )

    if (return_target_requests):
        return ra, dec, gmag, real_ids_int, internal_to_special_name, targets_internal, target_requests

    return ra, dec, gmag, real_ids_int, internal_to_special_name, targets_internal


# --- Helper: on-sphere separation in arcsec ------------------------------------
def separation_arcsec(
    ra_deg_target,
    dec_deg_target,
    ra_deg_contaminant,
    dec_deg_contaminant
):
    """
    Compute on-sphere separation between target and contaminants, in arcseconds.

    Uses the haversine formula in radians, then converts to degrees and arcsec.
    """
    ra_rad_target = np.deg2rad(ra_deg_target)
    dec_rad_target = np.deg2rad(dec_deg_target)
    ra_rad_contaminant = np.deg2rad(ra_deg_contaminant)
    dec_rad_contaminant = np.deg2rad(dec_deg_contaminant)

    sin_dec = np.sin((dec_rad_contaminant - dec_rad_target) / 2.0)
    sin_ra = np.sin((ra_rad_contaminant - ra_rad_target) / 2.0)

    a = sin_dec**2 + np.cos(dec_rad_target) * np.cos(dec_rad_contaminant) * sin_ra**2
    angle = 2.0 * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))

    return np.rad2deg(angle) * 3600.0


# --- Target processing helpers -------------------------------------------------
def source_id_from_internal_id(
    internal_id: int,
    real_ids_int: np.ndarray,
    internal_to_special_name: dict[int, str],
) -> str:
    """Resolve an internal 1-based ID to the original external source ID."""
    special_name = internal_to_special_name.get(internal_id)
    if (special_name is not None):
        return special_name

    index = internal_id - 1
    if (index < 0 or index >= real_ids_int.shape[0]):
        return ""

    numeric_id = int(real_ids_int[index])
    return str(numeric_id) if (numeric_id >= 0) else ""


def empty_target_result(source_id: str, ra: float, dec: float, magnitude: float) -> dict:
    """Create the stable no-contaminant result shape used by query output."""
    return TargetResult(
        source_id=source_id,
        ra=ra,
        dec=dec,
        phot_g_mean_mag=(magnitude if np.isfinite(magnitude) else None),
        flux_fraction_selected=0.0,
        flux_fraction_all_neighbors=0.0,
        flux_fraction_extra=0.0,
        num_neighbors_in_radius=0,
        num_contaminants_selected=0,
        num_contaminants=0,
        contaminants=[],
    ).__dict__


def unresolved_target_result(source_id: str, status: str) -> dict:
    """Represent a requested target that could not be evaluated against the index."""
    return {
        "source_id": source_id,
        "status": status,
        "ra": None,
        "dec": None,
        "phot_g_mean_mag": None,
        "flux_fraction_selected": None,
        "flux_fraction_all_neighbors": None,
        "flux_fraction_extra": None,
        "num_neighbors_in_radius": None,
        "num_contaminants_selected": None,
        "num_contaminants": None,
        "contaminants": [],
    }


def valid_neighbor_indices(neighbor_internal_ids: np.ndarray, number_of_sources: int) -> np.ndarray:
    """Convert 1-based neighbour IDs to valid zero-based catalogue positions."""
    candidate_indices = np.asarray(neighbor_internal_ids, dtype=np.int64) - 1
    return candidate_indices[(candidate_indices >= 0) & (candidate_indices < number_of_sources)]


def calculate_flux_fraction_extra(
    target_magnitude: float,
    contaminant_magnitudes: np.ndarray,
    selected_contaminants: np.ndarray,
) -> float:
    """Return extra contaminant flux as a percentage of the target flux."""
    if (not np.isfinite(target_magnitude) or not np.any(selected_contaminants)):
        return 0.0

    selected_magnitudes = contaminant_magnitudes[selected_contaminants]
    valid_magnitudes = selected_magnitudes[np.isfinite(selected_magnitudes)]
    if (valid_magnitudes.size == 0):
        return 0.0

    flux_ratios = 10.0 ** (-0.4 * (valid_magnitudes - target_magnitude))
    return float(flux_ratios[np.isfinite(flux_ratios)].sum() * 100.0)


def build_contaminant_records(
    contaminant_indices: np.ndarray,
    contaminant_magnitudes: np.ndarray,
    contaminant_separations: np.ndarray,
    selected_mask: np.ndarray,
    ra: np.ndarray,
    dec: np.ndarray,
    real_ids_int: np.ndarray,
    internal_to_special_name: dict[int, str],
) -> list[dict]:
    """Build public contaminant records from selected catalogue positions."""
    contaminants: list[dict] = []

    for local_index in np.flatnonzero(selected_mask):
        catalogue_index = int(contaminant_indices[local_index])
        magnitude = float(contaminant_magnitudes[local_index])
        contaminants.append(
            Contaminant(
                source_id=source_id_from_internal_id(
                    catalogue_index + 1,
                    real_ids_int,
                    internal_to_special_name,
                ),
                ra=float(ra[catalogue_index]),
                dec=float(dec[catalogue_index]),
                phot_g_mean_mag=(magnitude if np.isfinite(magnitude) else None),
                sep_arcsec=float(contaminant_separations[local_index]),
            ).__dict__
        )

    return contaminants


def process_target(
    internal_target: int,
    offsets: np.ndarray,
    neighbors_mm: np.ndarray,
    ra: np.ndarray,
    dec: np.ndarray,
    gmag: Optional[np.ndarray],
    real_ids_int: np.ndarray,
    internal_to_special_name: dict[int, str],
    field_of_view_arcsec: float,
    delta_mag: float,
    neighbor_separations_mm: Optional[np.ndarray] = None,
) -> dict | None:
    """Evaluate one target while keeping numerical work separate from loop orchestration."""
    number_of_sources = ra.shape[0]
    if (internal_target < 1 or internal_target > number_of_sources):
        logger.warning("internal_target %s out of range; skipping.", internal_target)
        return None

    target_index = internal_target - 1
    target_ra = float(ra[target_index])
    target_dec = float(dec[target_index])
    target_magnitude = float(gmag[target_index]) if (gmag is not None) else np.nan
    source_id = source_id_from_internal_id(internal_target, real_ids_int, internal_to_special_name)

    start = int(offsets[target_index])
    end = int(offsets[target_index + 1])
    if (start == end):
        return empty_target_result(source_id, target_ra, target_dec, target_magnitude)

    neighbor_internal_ids = np.asarray(neighbors_mm[start:end], dtype=np.int64)
    candidate_indices = neighbor_internal_ids - 1
    valid_mask = (candidate_indices >= 0) & (candidate_indices < number_of_sources)
    contaminant_indices = candidate_indices[valid_mask]
    if (contaminant_indices.size == 0):
        return empty_target_result(source_id, target_ra, target_dec, target_magnitude)

    contaminant_ra = ra[contaminant_indices]
    contaminant_dec = dec[contaminant_indices]
    if (gmag is None):
        contaminant_magnitudes = np.full(contaminant_indices.shape, np.nan, dtype=np.float64)
    else:
        contaminant_magnitudes = np.asarray(gmag[contaminant_indices], dtype=np.float64)

    if (neighbor_separations_mm is None):
        contaminant_separations = separation_arcsec(
            target_ra,
            target_dec,
            contaminant_ra,
            contaminant_dec,
        )
    else:
        contaminant_separations = np.asarray(
            neighbor_separations_mm[start:end],
            dtype=np.float64,
        )[valid_mask]
    inside_field_of_view = contaminant_separations <= field_of_view_arcsec
    selected_mask = inside_field_of_view & ((contaminant_magnitudes - target_magnitude) <= delta_mag)
    flux_fraction_selected = calculate_flux_fraction_extra(
        target_magnitude,
        contaminant_magnitudes,
        selected_mask,
    )
    flux_fraction_all_neighbors = calculate_flux_fraction_extra(
        target_magnitude,
        contaminant_magnitudes,
        inside_field_of_view,
    )

    contaminants = build_contaminant_records(
        contaminant_indices,
        contaminant_magnitudes,
        contaminant_separations,
        selected_mask,
        ra,
        dec,
        real_ids_int,
        internal_to_special_name,
    )

    return TargetResult(
        source_id=source_id,
        ra=target_ra,
        dec=target_dec,
        phot_g_mean_mag=(target_magnitude if np.isfinite(target_magnitude) else None),
        flux_fraction_selected=round(flux_fraction_selected, 2),
        flux_fraction_all_neighbors=round(flux_fraction_all_neighbors, 2),
        flux_fraction_extra=round(flux_fraction_selected, 2),
        num_neighbors_in_radius=int(np.count_nonzero(inside_field_of_view)),
        num_contaminants_selected=len(contaminants),
        num_contaminants=len(contaminants),
        contaminants=contaminants,
    ).__dict__


def loop_over_targets(
    offsets: np.ndarray,
    neighbors_mm: np.ndarray,
    ra: np.ndarray,
    dec: np.ndarray,
    gmag: Optional[np.ndarray],
    real_ids_int: np.memmap,
    internal_to_special_name: dict[int, str],
    field_of_view_arcsec: float,
    delta_mag: float,
    targets_internal: list[int],
    neighbor_separations_mm: Optional[np.ndarray] = None,
) -> list[dict]:
    """Evaluate configured targets while leaving one-target logic independently testable."""
    total_targets = len(targets_internal)
    if (total_targets == 0):
        progress_bar(100, "[processing targets]", complete=True)
        return []

    results: list[dict] = []
    for processed_count, internal_target in enumerate(targets_internal, start=1):
        result = process_target(
            int(internal_target),
            offsets,
            neighbors_mm,
            ra,
            dec,
            gmag,
            real_ids_int,
            internal_to_special_name,
            field_of_view_arcsec,
            delta_mag,
            neighbor_separations_mm,
        )
        if (result is not None):
            results.append(result)

        progress_bar(
            int(round((processed_count / float(total_targets)) * 100.0)),
            "[processing targets]",
            complete=(processed_count == total_targets),
        )

    return results


def merge_unresolved_target_results(
    evaluated_results: list[dict],
    target_requests: list[TargetRequest],
) -> list[dict]:
    """Return results in requested-target order, including missing/invalid rows."""
    evaluated_iter = iter(evaluated_results)
    merged: list[dict] = []
    for request in target_requests:
        if (request.status == "found"):
            merged.append(next(evaluated_iter))
        else:
            merged.append(unresolved_target_result(request.source_id, request.status))
    return merged

# --- Save results to JSON ------------------------------------------------------
def save_results_to_json(results: list, json_path: str) -> str:
    """
    Save the list of TargetResult dicts to the specified JSON file.

    Parameters
    ----------
    results : list[dict]
        List of TargetResult.__dict__ entries.

    json_path : str
        Output JSON path.

    Returns
    -------
    json_path : str
        Path to the written JSON file.
    """
    with open(json_path, "x", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return json_path


def query_metadata_path(result_json_path: str | Path) -> Path:
    """Return the reproducibility sidecar path for one query-result JSON file."""
    result_path = Path(result_json_path)
    return result_path.parent / "metadata" / f"{result_path.stem}_metadata.json"


def save_query_metadata(
    metadata_path: str | Path,
    runtime_plan: QueryRuntimePlan,
    result_json_path: str | Path,
    config_path: str | Path | None,
    processed_targets: int,
) -> str:
    """Save a non-breaking sidecar with the settings needed to reproduce a query."""
    selected_config_path = None if (config_path is None) else str(Path(config_path).resolve())
    payload = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "photo_cat_version": __version__,
        "config_path": selected_config_path,
        "result_json": str(Path(result_json_path).resolve()),
        "query": asdict(runtime_plan.config),
        "processed_targets": processed_targets,
        "index_manifest": asdict(runtime_plan.manifest),
        "contamination_model": {
            "kind": "catalogue_aperture_flux_ratio",
            "summary": (
                "Sources are selected within the configured circular angular query radius "
                "and delta-magnitude limit; flux_fraction_selected is computed from catalogue "
                "magnitude ratios for the selected sources, while flux_fraction_all_neighbors "
                "uses every valid neighbour inside the circular query radius."
            ),
            "not_included": [
                "instrumental PSF convolution",
                "detector pixel response or aperture weighting",
                "wavelength-dependent transformation between catalogue and mission bandpasses",
                "non-uniform contamination from bright sources outside the configured aperture",
            ],
        },
    }
    atomic_write_json(metadata_path, payload)
    return str(metadata_path)


# ============================================================
# MAIN EXECUTION
# ============================================================

def main(config_path: str | Path | None = None) -> int:
    """Run a contamination query after configuration and runtime-path validation succeed."""
    config_query = load_config("query_contamination_from_index", config_path)
    if (not isinstance(config_query, QueryConfig)):
        raise RuntimeError("Failed to load query configuration.")

    runtime_plan = prepare_query_runtime(config_query)
    paths = runtime_plan.paths
    output_json = str(runtime_plan.output_json)

    # ---------------- LOAD INDEX DATA --------------
    logger.info("Loading index data...")

    with ActivityBar("[loading index arrays]"):
        offsets = np.load(paths.offsets, allow_pickle=False)
    neighbors_path = paths.neighbors_ids

    total_neighbors = int(offsets[-1])
    logger.info(f"Total neighbor entries: {total_neighbors:,}")

    with ActivityBar("[opening neighbour memory map]"):
        if (total_neighbors == 0):
            neighbors_mm = np.empty(0, dtype=np.int64)
        else:
            neighbors_mm = np.memmap(
                neighbors_path,
                dtype=np.int64,
                mode='r',
                shape=(total_neighbors,)
            )
    logger.info("Index data loaded.")

    neighbor_separations_mm: np.ndarray | None = None
    if (runtime_plan.manifest.calculate_separations):
        if (total_neighbors == 0):
            neighbor_separations_mm = np.empty(0, dtype=np.float64)
        else:
            neighbor_separations_mm = np.memmap(
                paths.neighbors_seps,
                dtype=np.float64,
                mode="r",
                shape=(total_neighbors,),
            )

    # ---------------- LOAD CATALOG ARRAYS ----------
    (
        ra,
        dec,
        gmag,
        real_ids_int,
        internal_to_special_name,
        targets_internal,
        target_requests,
    ) = load_catalog_arrays(
        paths,
        config_query.TARGETS_INPUT,
        config_query.targets,
        config_query.target_source_id_column,
        return_target_requests=True,
    )
    if (not targets_internal and not config_query.include_missing_targets):
        invalid_targets = [request.source_id for request in target_requests if request.status == "invalid_target_id"]
        missing_targets = [request.source_id for request in target_requests if request.status == "missing_from_index"]
        details: list[str] = []
        if (invalid_targets):
            details.append(f"Unrecognised target values: {target_id_preview(invalid_targets)}")
        if (missing_targets):
            details.append(f"Target values not found in the index: {target_id_preview(missing_targets)}")

        raise ValueError(
            "None of the configured targets were found in the built index.\n\n"
            + "\n".join(details)
            + "\n\nMake sure Targets CSV/source_id values come from the same catalog used to build the index."
        )

    
    # ---------------- RUN CONTAMINATION LOOP -------
    results = loop_over_targets(
        offsets=offsets,
        neighbors_mm=neighbors_mm,
        ra=ra,
        dec=dec,
        gmag=gmag,
        real_ids_int=real_ids_int,
        internal_to_special_name=internal_to_special_name,
        field_of_view_arcsec=config_query.field_of_view_arcsec,
        delta_mag=config_query.delta_mag,
        targets_internal=targets_internal,
        neighbor_separations_mm=neighbor_separations_mm,
    )
    if (config_query.include_missing_targets):
        results = merge_unresolved_target_results(results, target_requests)

    # ---------------- SAVE RESULTS -----------------
    with ActivityBar("[saving JSON results]"):
        json_path = save_results_to_json(results, output_json)
        metadata_path = save_query_metadata(
            query_metadata_path(json_path),
            runtime_plan,
            json_path,
            config_path,
            len(results),
        )

    evaluated_results = [r for r in results if (r.get("status", "found") == "found")]
    targets_with_contaminants = sum(int(r.get("num_contaminants") or 0) > 0 for r in evaluated_results)
    targets_without_contaminants = sum(int(r.get("num_contaminants") or 0) == 0 for r in evaluated_results)

    logger.info("")
    logger.info(f"Results saved to: {json_path}")
    logger.info(f"Run metadata saved to: {metadata_path}")
    logger.info(
        f"Targets processed: {len(results)} "
        f"(with contaminants: {targets_with_contaminants}, "
        f"without contaminants: {targets_without_contaminants}, "
        f"unresolved: {len(results) - len(evaluated_results)})"
    )

    return 0


if (__name__ == "__main__"):
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.error("Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        logger.error("ERROR:\n%s", exc)
        raise SystemExit(1)
