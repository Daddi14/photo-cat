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

    def numeric_real_to_internal(real_id_int: int) -> Optional[int]:
        """
        Find internal_id for a numeric real_id using a binary search over the sorted
        arrays (numeric_real_ids_sorted / numeric_internal_ids_sorted).
        """
        pos = np.searchsorted(numeric_real_ids_sorted, real_id_int)
        if pos < numeric_real_ids_sorted.size and numeric_real_ids_sorted[pos] == real_id_int:
            return int(numeric_internal_ids_sorted[pos])
        return None

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

        internal = numeric_real_to_internal(val)
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


# --- Main processing loop ------------------------------------------------------
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
    targets_internal: list[int]
) -> list:
    """
    Main contamination loop using compact arrays and memmapped neighbors.

    Parameters
    ----------
    offsets : numpy.ndarray
        CSR offsets array (N+1,). For row i, neighbors are in slice:
            neighbors_mm[offsets[i] : offsets[i+1]]

    neighbors_mm : numpy.memmap
        Memmapped neighbors_ids.bin, containing internal_ids of neighbors.

    ra, dec : numpy.ndarray
        float64 arrays (or memmaps) of length N, indexed by (internal_id - 1).

    gmag : numpy.ndarray or None
        float64 array (or memmap) of G magnitudes; None if not available.

    real_ids_int : numpy.memmap
        int64 array of length N, numeric real IDs or -1 for special IDs.

    internal_to_special_name : dict[int, str]
        Mapping from internal_id to special string source_id.

    field_of_view_arcsec : float
        FoV radius used to select contaminants.

    delta_mag : float
        Magnitude difference threshold for selecting contaminants.

    targets_internal : list[int]
        List of internal_ids for the targets to process.

    Returns
    -------
    results : list[dict]
        List of TargetResult.__dict__ for each processed target.
    """
    results = []
    n_sources = ra.shape[0]

    def internal_to_real_string(internal_id: int) -> str:
        """
        Convert a internal_id (1..N) to its real external source_id string.

        Logic:
            - if internal_id in internal_to_special_name -> use special string
            - else use real_ids_int[internal_id - 1] if >= 0
        """
        name = internal_to_special_name.get(internal_id)
        if name is not None:
            return name

        idx = internal_id - 1
        val = int(real_ids_int[idx])
        if val >= 0:
            return str(val)

        return ""

    total_targets = len(targets_internal)
    if (total_targets <= 0):
        progress_bar(100, "[processing targets]", complete=True)
        return results

    processed_targets = 0

    def update_target_progress() -> None:
        nonlocal processed_targets
        processed_targets += 1
        progress_bar(
            int(round((processed_targets / float(total_targets)) * 100.0)),
            "[processing targets]",
            complete=(processed_targets == total_targets),
        )

    for internal_target in targets_internal:
        internal_target = int(internal_target)

        # Sanity check: internal_id must be in [1, N].
        if internal_target < 1 or internal_target > n_sources:
            logger.warning(f"internal_target {internal_target} out of range; skipping.")
            update_target_progress()
            continue

        target_index = internal_target - 1

        start = int(offsets[target_index])
        end = int(offsets[target_index + 1])

        target_ra = float(ra[target_index])
        target_dec = float(dec[target_index])
        target_mag = float(gmag[target_index]) if gmag is not None else np.nan

        source_id_str = internal_to_real_string(internal_target)

        # No neighbors: quick exit with zero contaminants and zero extra flux.
        if start == end:
            results.append(
                TargetResult(
                    source_id=source_id_str,
                    ra=target_ra,
                    dec=target_dec,
                    phot_g_mean_mag=(target_mag if np.isfinite(target_mag) else None),
                    flux_fraction_extra=0.0,
                    num_contaminants=0,
                    contaminants=[]
                ).__dict__
            )
            update_target_progress()
            continue

        # Extract internal_ids of neighbors for this target: shape (k,).
        contaminant_internal_ids = neighbors_mm[start:end].astype(np.int64)
        contaminant_indices = contaminant_internal_ids - 1  # convert to 0-based row indices

        # Defensive mask: neighbors must reference valid rows in [0, N).
        valid_mask = (contaminant_indices >= 0) & (contaminant_indices < n_sources)
        if not np.any(valid_mask):
            results.append(
                TargetResult(
                    source_id=source_id_str,
                    ra=target_ra,
                    dec=target_dec,
                    phot_g_mean_mag=(target_mag if np.isfinite(target_mag) else None),
                    flux_fraction_extra=0.0,
                    num_contaminants=0,
                    contaminants=[]
                ).__dict__
            )
            update_target_progress()
            continue

        contaminant_indices = contaminant_indices[valid_mask]

        contaminant_ra = ra[contaminant_indices]
        contaminant_dec = dec[contaminant_indices]

        if gmag is not None:
            contaminant_magnitudes_all = gmag[contaminant_indices]
        else:
            contaminant_magnitudes_all = np.full_like(
                contaminant_ra,
                np.nan,
                dtype=np.float64
            )

        # Angular separations (arcsec) between target and each neighbor.
        contaminant_separations = separation_arcsec(
            target_ra,
            target_dec,
            contaminant_ra,
            contaminant_dec
        )

        # Mask contaminants inside the FoV.
        mask_fov = contaminant_separations <= field_of_view_arcsec

        # Compute target flux via Pogson's law (F ∝ 10^(-0.4 * mag)).
        target_flux = 10.0 ** (-0.4 * target_mag) if np.isfinite(target_mag) else np.nan
        flux_fraction_extra = 0.0

        if np.isfinite(target_flux) and np.any(mask_fov):
            magnitudes_in_fov = contaminant_magnitudes_all[mask_fov]
            valid_magnitudes_mask = np.isfinite(magnitudes_in_fov)

            if np.any(valid_magnitudes_mask):
                contaminant_fluxes_all = 10.0 ** (-0.4 * magnitudes_in_fov[valid_magnitudes_mask])
                if target_flux > 0.0:
                    flux_fraction_extra = (contaminant_fluxes_all.sum() / target_flux) * 100.0
                else:
                    flux_fraction_extra = 0.0

        # Δmag selection: keep contaminants with mag - mag_target <= delta_mag.
        delta_g = contaminant_magnitudes_all - target_mag
        sel_mask = mask_fov & (delta_g <= delta_mag)
        sel_idx = np.where(sel_mask)[0]

        contaminants = []
        for i in sel_idx:
            idx = int(contaminant_indices[i])
            neighbor_internal_id = idx + 1

            contaminants.append(
                Contaminant(
                    source_id=internal_to_real_string(neighbor_internal_id),
                    ra=float(ra[idx]),
                    dec=float(dec[idx]),
                    phot_g_mean_mag=float(gmag[idx]) if gmag is not None else None,
                    sep_arcsec=float(contaminant_separations[i])
                ).__dict__
            )

        results.append(
            TargetResult(
                source_id=source_id_str,
                ra=target_ra,
                dec=target_dec,
                phot_g_mean_mag=(target_mag if np.isfinite(target_mag) else None),
                flux_fraction_extra=round(float(flux_fraction_extra), 2),
                num_contaminants=len(contaminants),
                contaminants=contaminants
            ).__dict__
        )

        update_target_progress()

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
