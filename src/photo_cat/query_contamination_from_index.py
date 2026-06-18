#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""
query_contamination_from_index.py

Purpose
-------
Consume the CSR-like neighbor index built by build_neighbors_index.py and
compute contamination metrics for a list of target stars.

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
            * names    : object[:] -> original string IDs (e.g. "HD 216608A")

    - master_catalog.parquet
        Full catalog for inspection (not used in this low-memory query path).

Core outputs per target
-----------------------
For each target source_id (real external ID, numeric or string):

    - source_id            : real ID used as input
    - ra, dec              : coordinates of the target
    - phot_g_mean_mag      : G magnitude of the target
    - flux_fraction_extra  : percentage of extra flux from contaminants inside
                             the field of view (FoV), relative to target flux
    - num_contaminants     : number of neighbors that satisfy FoV + Δmag cut
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
        Angular radius (in arcsec) defining the field of view.

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
    - Un unico file JSON, salvato in:
          INDEX_DIR / "output" / "<basename>_FoV..._dmag..._YYYYMMDD_HHMM.json"
"""

import csv
import os
import json
from datetime import datetime
from typing import Optional, Dict

import numpy as np
import pandas as pd

from .target_result import TargetResult
from .contaminant import Contaminant
from .logger_setup import get_logger
from .load_config import load_config
from .pipeline_display import ActivityBar, progress_bar


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




def validate_index_directory(index_dir: str) -> None:
    required_files = [
        "offsets.npy",
        "neighbors_ids.bin",
        "ra.npy",
        "dec.npy",
        "phot_g_mean_mag.npy",
        "real_ids_int.npy",
        "special_ids.npz",
    ]
    missing_files = [name for name in required_files if (not os.path.isfile(os.path.join(index_dir, name)))]

    if (missing_files):
        raise FileNotFoundError(
            "Query index folder is not ready.\n\n"
            f"Selected index folder:\n{index_dir}\n\n"
            "Missing required index files:\n"
            + "\n".join(f"- {name}" for name in missing_files)
            + "\n\nRun the build step first, or select the correct Output/index folder."
        )

# --- Helper: create output JSON path ------------------------------------------
def create_output_json_path(
    TARGETS_INPUT: Optional[str],
    INDEX_DIR: str,
    field_of_view_arcsec: float,
    delta_mag: float
    ) -> str:
    """
    Build a timestamped JSON output path under INDEX_DIR/output.

    The file name encodes:
        - input target file name (or "manual_targets")
        - FoV radius
        - delta_mag threshold
        - timestamp (YYYYMMDD_HHMM)

    The directory INDEX_DIR/output is created if it does not exist.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    if TARGETS_INPUT:
        base_name = os.path.splitext(os.path.basename(TARGETS_INPUT))[0]
    else:
        base_name = "manual_targets"

    output_dir = os.path.join(INDEX_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{base_name}_FoV{int(field_of_view_arcsec)}_dmag{int(delta_mag)}_{timestamp}.json"
    return os.path.join(output_dir, filename)


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


# --- Load catalog and targets (low-memory path) --------------------------------
def load_catalog_arrays(
    INDEX_DIR: str,
    TARGETS_INPUT: Optional[str] = None,
    targets: Optional[list] = None,
    target_source_id_column: str = "source_id"
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
    INDEX_DIR : str
        Directory with ra.npy, dec.npy, phot_g_mean_mag.npy,
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
    # Numeric columns as memmap (do not load fully into RAM).
    ra = np.load(os.path.join(INDEX_DIR, "ra.npy"), mmap_mode="r")
    dec = np.load(os.path.join(INDEX_DIR, "dec.npy"), mmap_mode="r")

    gmag = None
    gmag_path = os.path.join(INDEX_DIR, "phot_g_mean_mag.npy")
    if os.path.exists(gmag_path):
        gmag = np.load(gmag_path, mmap_mode="r")

    n_sources = ra.shape[0]
    logger.info(f"Loaded coordinates arrays for {n_sources:,} sources from index.")

    # Numeric real IDs: one per row, -1 where IDs are non-numeric.
    real_ids_int_path = os.path.join(INDEX_DIR, "real_ids_int.npy")
    real_ids_int = np.load(real_ids_int_path, mmap_mode="r")

    # Special IDs: few rows with non-numeric names (e.g. "HD 216608A").
    special_ids_path = os.path.join(INDEX_DIR, "special_ids.npz")
    special = np.load(special_ids_path, allow_pickle=True)
    special_internal_ids = special["internal_ids"].astype(np.int64)
    special_names = special["names"].astype(str)

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
    valid_mask = real_ids_int >= 0
    numeric_indices = np.nonzero(valid_mask)[0].astype(np.int64)
    numeric_real_ids = real_ids_int[valid_mask].astype(np.int64)

    sort_idx = np.argsort(numeric_real_ids)
    numeric_real_ids_sorted = numeric_real_ids[sort_idx]
    numeric_internal_ids_sorted = numeric_indices[sort_idx] + 1  # internal_id = idx + 1

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

    # --- Resolve target internal IDs (special IDs first, then numeric) ---
    targets_internal: list[int] = []
    invalid_targets: list[str] = []
    missing_targets: list[str] = []

    for t in targets_real:
        if t in name_to_internal_special:
            targets_internal.append(name_to_internal_special[t])
            continue

        try:
            val = int(t)
        except (ValueError, TypeError):
            invalid_targets.append(str(t))
            continue

        internal = find_numeric_internal_id(
            numeric_real_ids_sorted,
            numeric_internal_ids_sorted,
            val,
        )
        if internal is not None:
            targets_internal.append(internal)
        else:
            missing_targets.append(str(t))

    if (invalid_targets):
        preview = ", ".join(invalid_targets[:8])
        suffix = "" if (len(invalid_targets) <= 8) else f", ... (+{len(invalid_targets) - 8} more)"
        logger.warning(
            "Skipped %d target value(s) because they were neither numeric source_id values nor recognised special IDs. Examples: %s%s",
            len(invalid_targets),
            preview,
            suffix
        )

    if (missing_targets):
        preview = ", ".join(missing_targets[:8])
        suffix = "" if (len(missing_targets) <= 8) else f", ... (+{len(missing_targets) - 8} more)"
        logger.warning(
            "Skipped %d target value(s) because they were not found in the built index. Examples: %s%s",
            len(missing_targets),
            preview,
            suffix
        )

    logger.info("Loaded %d target(s) for analysis.", len(targets_internal))

    if (not targets_internal):
        raise ValueError(
            "None of the configured targets were found in the built index.\n\n"
            "Make sure Targets CSV/source_id values come from the same catalog used to build the index."
        )

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
        flux_fraction_extra=0.0,
        num_contaminants=0,
        contaminants=[],
    ).__dict__


def valid_neighbor_indices(neighbor_internal_ids: np.ndarray, number_of_sources: int) -> np.ndarray:
    """Convert 1-based neighbour IDs to valid zero-based catalogue positions."""
    candidate_indices = np.asarray(neighbor_internal_ids, dtype=np.int64) - 1
    return candidate_indices[(candidate_indices >= 0) & (candidate_indices < number_of_sources)]


def calculate_flux_fraction_extra(
    target_magnitude: float,
    contaminant_magnitudes: np.ndarray,
    inside_field_of_view: np.ndarray,
) -> float:
    """Return extra contaminant flux as a percentage of the target flux."""
    if (not np.isfinite(target_magnitude) or not np.any(inside_field_of_view)):
        return 0.0

    target_flux = 10.0 ** (-0.4 * target_magnitude)
    if (not np.isfinite(target_flux) or target_flux <= 0.0):
        return 0.0

    magnitudes_in_fov = contaminant_magnitudes[inside_field_of_view]
    valid_magnitudes = magnitudes_in_fov[np.isfinite(magnitudes_in_fov)]
    if (valid_magnitudes.size == 0):
        return 0.0

    contaminant_fluxes = 10.0 ** (-0.4 * valid_magnitudes)
    return float((contaminant_fluxes.sum() / target_flux) * 100.0)


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

    contaminant_indices = valid_neighbor_indices(neighbors_mm[start:end], number_of_sources)
    if (contaminant_indices.size == 0):
        return empty_target_result(source_id, target_ra, target_dec, target_magnitude)

    contaminant_ra = ra[contaminant_indices]
    contaminant_dec = dec[contaminant_indices]
    if (gmag is None):
        contaminant_magnitudes = np.full(contaminant_indices.shape, np.nan, dtype=np.float64)
    else:
        contaminant_magnitudes = np.asarray(gmag[contaminant_indices], dtype=np.float64)

    contaminant_separations = separation_arcsec(
        target_ra,
        target_dec,
        contaminant_ra,
        contaminant_dec,
    )
    inside_field_of_view = contaminant_separations <= field_of_view_arcsec
    flux_fraction_extra = calculate_flux_fraction_extra(
        target_magnitude,
        contaminant_magnitudes,
        inside_field_of_view,
    )

    selected_mask = inside_field_of_view & ((contaminant_magnitudes - target_magnitude) <= delta_mag)
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
        flux_fraction_extra=round(flux_fraction_extra, 2),
        num_contaminants=len(contaminants),
        contaminants=contaminants,
    ).__dict__


def loop_over_targets(
    offsets: np.ndarray,
    neighbors_mm: np.memmap,
    ra: np.ndarray,
    dec: np.ndarray,
    gmag: Optional[np.ndarray],
    real_ids_int: np.memmap,
    internal_to_special_name: dict[int, str],
    field_of_view_arcsec: float,
    delta_mag: float,
    targets_internal: list[int],
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
        )
        if (result is not None):
            results.append(result)

        progress_bar(
            int(round((processed_count / float(total_targets)) * 100.0)),
            "[processing targets]",
            complete=(processed_count == total_targets),
        )

    return results

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
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    return json_path


# ============================================================
# MAIN EXECUTION
# ============================================================

def main() -> int:
    # ---------------- CONFIG IMPORT ----------------
    config_query = load_config("query_contamination_from_index")

    validate_index_directory(config_query.INDEX_DIR)

    # ---------------- OUTPUT PATH (JSON ONLY) ------
    OUTPUT_JSON = create_output_json_path(
        config_query.TARGETS_INPUT,
        config_query.INDEX_DIR,
        config_query.field_of_view_arcsec,
        config_query.delta_mag
    )

    # ---------------- LOAD INDEX DATA --------------
    logger.info("Loading index data...")

    with ActivityBar("[loading index arrays]"):
        offsets = np.load(os.path.join(config_query.INDEX_DIR, "offsets.npy"))
    neighbors_path = os.path.join(config_query.INDEX_DIR, "neighbors_ids.bin")

    total_neighbors = int(offsets[-1])
    logger.info(f"Total neighbor entries: {total_neighbors:,}")

    with ActivityBar("[opening neighbour memory map]"):
        neighbors_mm = np.memmap(
            neighbors_path,
            dtype=np.int64,
            mode='r',
            shape=(total_neighbors,)
        )
    logger.info("Index data loaded.")

    # ---------------- LOAD CATALOG ARRAYS ----------
    ra, dec, gmag, real_ids_int, internal_to_special_name, targets_internal = load_catalog_arrays(
        config_query.INDEX_DIR,
        config_query.TARGETS_INPUT,
        config_query.targets,
        config_query.target_source_id_column
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
        targets_internal=targets_internal
    )

    # ---------------- SAVE RESULTS -----------------
    with ActivityBar("[saving JSON results]"):
        json_path = save_results_to_json(results, OUTPUT_JSON)

    targets_with_contaminants = sum(r["num_contaminants"] > 0 for r in results)
    targets_without_contaminants = sum(r["num_contaminants"] == 0 for r in results)

    logger.info("")
    logger.info(f"Results saved to: {json_path}")
    logger.info(
        f"Targets processed: {len(results)} "
        f"(with contaminants: {targets_with_contaminants}, "
        f"without contaminants: {targets_without_contaminants})"
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
