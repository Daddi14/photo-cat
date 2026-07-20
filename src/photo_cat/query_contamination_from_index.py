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
estimates flux ratios from configured catalogue magnitude columns. An optional
circular Gaussian PSF model weights each source by its radial flux decay and
estimates leakage out to a PSF-derived influence radius. It does not perform
spatially varying or asymmetric PSF
convolution, detector-pixel modelling, scattered-light modelling, or full
spectral/passband integration. An optional provenance-tracked empirical colour
transformation can estimate a calibrated mission band. Treat the result as a
contamination risk-assessment / target-screening metric unless calibrated
mission inputs support the selected model.

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

    - contamination_model.gaussian_fwhm_arcsec / contamination_model.influence_sigma
        Gaussian PSF width and the number of standard deviations still counted.
        Their product is the outer neighbour radius used to model weighted
        leakage from sources outside the aperture.

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
          INDEX_DIR / "results" / "<basename>_FoV..._dmag..._YYYYMMDD_HHMMSS_microseconds.json"
    - One reproducibility metadata sidecar, saved under:
          INDEX_DIR / "results" / "metadata" / "<result_stem>_metadata.json"
"""

import csv
import os
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Dict

import numpy as np
import pandas as pd
from scipy.stats import ncx2

from . import __version__
from .bandpass_transform import (
    BandpassTransformProfile,
    load_bandpass_profile,
    transform_magnitudes,
    transform_status_name,
)
from .index_manifest import (
    IndexManifest,
    atomic_write_json,
    load_index_manifest,
    validate_index_structure,
)
from .target_result import TargetResult
from .contaminant import Contaminant
from .logger_setup import get_logger
from .load_config import GAUSSIAN_FWHM_TO_SIGMA, ContaminationModelConfig, QueryConfig, load_config
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
    influence_radius = config.effective_influence_radius_arcsec
    if (influence_radius > manifest.max_radius_arcsec):
        logger.info(
            "Query influence radius (%.3f arcsec) exceeds the index build radius "
            "(%.3f arcsec); neighbours will be recomputed from the catalogue for the "
            "requested targets only.",
            influence_radius,
            manifest.max_radius_arcsec,
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


def empty_target_result(
    source_id: str,
    ra: float,
    dec: float,
    magnitude: float,
    contamination_model: ContaminationModelConfig | None = None,
    magnitude_bands: list[str] | None = None,
    bandpass_output_band: str | None = None,
    bandpass_profile_name: str | None = None,
    bandpass_status: str | None = None,
    target_magnitudes_by_band: dict[str, float | None] | None = None,
    aperture_radius_arcsec: float | None = None,
) -> dict:
    """Create the stable no-contaminant result shape used by query output."""
    contamination_model = contamination_model or ContaminationModelConfig()
    magnitude_bands = magnitude_bands or []
    result = TargetResult(
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
    result["contamination_model"] = contamination_model.mode
    result["flux_fraction_selected_by_band"] = {band: 0.0 for band in magnitude_bands}
    result["flux_fraction_all_neighbors_by_band"] = {band: 0.0 for band in magnitude_bands}
    result["flux_fraction_inside_aperture"] = 0.0
    result["flux_fraction_outside_aperture"] = 0.0
    result["flux_fraction_total_weighted"] = 0.0
    result["flux_fraction_outside_aperture_by_band"] = {band: 0.0 for band in magnitude_bands}
    result["flux_fraction_total_weighted_by_band"] = {band: 0.0 for band in magnitude_bands}
    result["num_neighbors_in_influence_radius"] = 0
    result["num_neighbors_outside_aperture"] = 0
    result["num_contaminants_outside_aperture"] = 0
    result["outside_aperture_contaminants"] = []
    result["bandpass_transformed_band"] = bandpass_output_band
    result["bandpass_transform_profile"] = bandpass_profile_name
    result["bandpass_transform_status"] = bandpass_status
    result["target_magnitudes_by_band"] = target_magnitudes_by_band or {}
    result["flux_fraction_selected_transformed"] = 0.0 if bandpass_output_band is not None else None
    result["flux_fraction_all_neighbors_transformed"] = 0.0 if bandpass_output_band is not None else None
    result["flux_fraction_outside_aperture_transformed"] = 0.0 if bandpass_output_band is not None else None
    result["flux_fraction_total_weighted_transformed"] = 0.0 if bandpass_output_band is not None else None
    result["psf_metrics"] = psf_aperture_metrics(
        magnitude,
        np.empty(0, dtype=np.float64),
        np.empty(0, dtype=bool),
        np.empty(0, dtype=np.float64),
        contamination_model,
        aperture_radius_arcsec,
    )
    return result


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
        "contamination_model": None,
        "flux_fraction_selected_by_band": {},
        "flux_fraction_all_neighbors_by_band": {},
        "flux_fraction_inside_aperture": None,
        "flux_fraction_outside_aperture": None,
        "flux_fraction_total_weighted": None,
        "flux_fraction_outside_aperture_by_band": {},
        "flux_fraction_total_weighted_by_band": {},
        "num_neighbors_in_influence_radius": None,
        "num_neighbors_outside_aperture": None,
        "num_contaminants_outside_aperture": None,
        "outside_aperture_contaminants": [],
        "bandpass_transformed_band": None,
        "bandpass_transform_profile": None,
        "bandpass_transform_status": None,
        "target_magnitudes_by_band": {},
        "flux_fraction_selected_transformed": None,
        "flux_fraction_all_neighbors_transformed": None,
        "flux_fraction_outside_aperture_transformed": None,
        "flux_fraction_total_weighted_transformed": None,
        "contaminants": [],
    }


def valid_neighbor_indices(neighbor_internal_ids: np.ndarray, number_of_sources: int) -> np.ndarray:
    """Convert 1-based neighbour IDs to valid zero-based catalogue positions."""
    candidate_indices = np.asarray(neighbor_internal_ids, dtype=np.int64) - 1
    return candidate_indices[(candidate_indices >= 0) & (candidate_indices < number_of_sources)]


def safe_band_name(band: str) -> str:
    """Return the normalized magnitude-band identifier used by build outputs."""
    import re

    safe = re.sub(r"[^0-9A-Za-z_]+", "_", str(band).strip().lower()).strip("_")
    if (safe == ""):
        raise ValueError("Magnitude band names cannot be empty.")
    return safe


def _gaussian_sigma_arcsec(fwhm_arcsec: float) -> float:
    """Convert a Gaussian FWHM in arcseconds to its standard deviation."""
    return float(fwhm_arcsec) / GAUSSIAN_FWHM_TO_SIGMA


PSF_MODEL_MODES = ("gaussian_psf",)


def psf_aperture_metrics(
    target_magnitude: float,
    contaminant_magnitudes: np.ndarray,
    selected_mask: np.ndarray,
    contaminant_separations: np.ndarray,
    model: ContaminationModelConfig,
    aperture_radius_arcsec: float | None,
) -> dict[str, float] | None:
    """Return integrated circular-Gaussian-PSF contamination metrics for one target.

    Only produced for the Gaussian PSF model (``gaussian_psf``),
    which is defined solely by the FWHM. All fluxes are expressed in units of the
    target's total flux. With sigma = FWHM / (2*sqrt(2*ln 2)) and a circular aperture
    of radius R centred on the target:

    - ``sigma_arcsec``  the PSF standard deviation the metrics were computed with,
      reported alongside ``fwhm_arcsec`` so the result is self-describing.
    - ``effective_target_flux``  F_target = fraction of the target's own flux that
      falls inside the aperture = 1 - exp(-R^2 / (2*sigma^2)).
    - ``effective_contaminating_flux``  F_cont = sum over the selected contaminants of
      captured_i * flux_ratio_i, where captured_i is the fraction of contaminant i's
      flux captured by the (offset) aperture and flux_ratio_i = 10^(-0.4*(m_i - m_t))
      is its total flux relative to the target.
    - ``contamination_ratio``  C = F_cont / F_target.
    - ``target_purity``  P = F_target / (F_target + F_cont).
    - ``contaminating_fraction``  1 - P.
    """
    if (model.mode not in PSF_MODEL_MODES or model.gaussian_fwhm_arcsec is None):
        return None
    if (not np.isfinite(target_magnitude) or aperture_radius_arcsec is None or aperture_radius_arcsec <= 0.0):
        return None

    sigma = _gaussian_sigma_arcsec(model.gaussian_fwhm_arcsec)
    radius_squared = (float(aperture_radius_arcsec) / sigma) ** 2
    effective_target_flux = float(ncx2.cdf(radius_squared, df=2, nc=0.0))
    if (not np.isfinite(effective_target_flux) or effective_target_flux <= 0.0):
        return None

    effective_contaminating_flux = 0.0
    selected = np.asarray(selected_mask, dtype=bool)
    if (np.any(selected)):
        selected_magnitudes = np.asarray(contaminant_magnitudes, dtype=np.float64)[selected]
        selected_separations = np.asarray(contaminant_separations, dtype=np.float64)[selected]
        valid = np.isfinite(selected_magnitudes) & np.isfinite(selected_separations)
        selected_magnitudes = selected_magnitudes[valid]
        selected_separations = selected_separations[valid]
        if (selected_magnitudes.size):
            flux_ratios = 10.0 ** (-0.4 * (selected_magnitudes - target_magnitude))
            captured = ncx2.cdf(radius_squared, df=2, nc=(selected_separations / sigma) ** 2)
            contributions = np.asarray(captured, dtype=np.float64) * flux_ratios
            effective_contaminating_flux = float(contributions[np.isfinite(contributions)].sum())

    total_flux = effective_target_flux + effective_contaminating_flux
    contamination_ratio = effective_contaminating_flux / effective_target_flux
    target_purity = (effective_target_flux / total_flux) if (total_flux > 0.0) else 1.0

    return {
        "fwhm_arcsec": round(float(model.gaussian_fwhm_arcsec), 6),
        "sigma_arcsec": round(sigma, 6),
        "aperture_radius_arcsec": round(float(aperture_radius_arcsec), 6),
        "effective_target_flux": round(effective_target_flux, 6),
        "effective_contaminating_flux": round(effective_contaminating_flux, 6),
        "contamination_ratio": round(contamination_ratio, 6),
        "target_purity": round(target_purity, 6),
        "contaminating_fraction": round(1.0 - target_purity, 6),
    }


def _top_hat_weights(
    separations_arcsec: np.ndarray,
    model: ContaminationModelConfig,
    aperture_radius_arcsec: float | None,
) -> np.ndarray:
    """Compatibility model: full weight inside the aperture, none beyond it."""
    if (aperture_radius_arcsec is None):
        return np.ones(separations_arcsec.shape, dtype=np.float64)
    return np.asarray(separations_arcsec <= aperture_radius_arcsec, dtype=np.float64)


def _gaussian_psf_weights(
    separations_arcsec: np.ndarray,
    model: ContaminationModelConfig,
    aperture_radius_arcsec: float | None,
) -> np.ndarray:
    """Radial Gaussian point-spread-function response, peaking at the centre.

    Each source's flux decays as exp(-r^2 / 2*sigma^2) with angular distance from
    the aperture centre, so a contaminant contributes less the further out it sits.
    """
    if (model.gaussian_fwhm_arcsec is None):
        raise ValueError("gaussian_fwhm_arcsec is required for gaussian_psf contamination weighting.")
    sigma = _gaussian_sigma_arcsec(model.gaussian_fwhm_arcsec)
    return np.exp(-0.5 * (separations_arcsec / sigma) ** 2)


# Registry of contamination-weighting models. Adding a model is a single entry here,
# and each weighter shares the (separations, model, aperture) signature so it can be
# selected by name without a branching dispatch.
CONTAMINATION_WEIGHTERS = {
    "top_hat": _top_hat_weights,
    "gaussian_psf": _gaussian_psf_weights,
}


def contamination_weights(
    separations_arcsec: np.ndarray,
    model: ContaminationModelConfig,
    aperture_radius_arcsec: float | None = None,
) -> np.ndarray:
    """Return per-neighbour aperture/PSF weights for the configured model."""
    weighter = CONTAMINATION_WEIGHTERS.get(model.mode)
    if (weighter is None):
        raise ValueError(f"Unsupported contamination model: {model.mode}")
    return weighter(separations_arcsec, model, aperture_radius_arcsec)


def manifest_magnitude_bands(manifest: IndexManifest) -> dict[str, dict[str, str]]:
    """Return magnitude-band metadata, defaulting legacy indexes to Gaia-G."""
    return manifest.magnitude_bands or {
        "gaia_g": {
            "catalog_column": "phot_g_mean_mag",
            "array_file": "phot_g_mean_mag.npy",
        }
    }


def resolve_requested_bands(requested_bands: list[str], manifest: IndexManifest) -> list[str]:
    """Validate requested contamination bands against the completed index manifest."""
    available = manifest_magnitude_bands(manifest)
    if (len(requested_bands) == 1 and requested_bands[0].lower() == "all"):
        return sorted(available)
    missing = [band for band in requested_bands if band not in available]
    if (missing):
        raise ValueError(
            "Requested contamination band(s) are not stored in this index: "
            + ", ".join(missing)
            + ". Available bands: "
            + ", ".join(sorted(available))
        )
    return requested_bands


def load_magnitude_arrays(index_dir: str | Path, manifest: IndexManifest, requested_bands: list[str]) -> dict[str, np.ndarray]:
    """Open requested magnitude arrays as safe NumPy memmaps."""
    available = manifest_magnitude_bands(manifest)
    arrays: dict[str, np.ndarray] = {}
    for band in requested_bands:
        array_file = available[band]["array_file"]
        array_path = Path(index_dir) / array_file
        try:
            arrays[band] = np.load(array_path, mmap_mode="r", allow_pickle=False)
        except (OSError, ValueError) as error:
            raise ValueError(f"Could not load magnitude band {band}: {array_path}") from error
        if (arrays[band].ndim != 1 or arrays[band].shape[0] != manifest.number_of_sources):
            raise ValueError(f"Magnitude band {band} does not match the completed index size.")
    return arrays


def calculate_flux_fraction_extra(
    target_magnitude: float,
    contaminant_magnitudes: np.ndarray,
    selected_contaminants: np.ndarray,
    weights: np.ndarray | None = None,
) -> float:
    """Return extra contaminant flux as a percentage of the target flux."""
    if (not np.isfinite(target_magnitude) or not np.any(selected_contaminants)):
        return 0.0

    selected_magnitudes = contaminant_magnitudes[selected_contaminants]
    selected_weights = (
        np.ones(selected_magnitudes.shape, dtype=np.float64)
        if (weights is None)
        else np.asarray(weights, dtype=np.float64)[selected_contaminants]
    )
    valid_mask = np.isfinite(selected_magnitudes) & np.isfinite(selected_weights)
    valid_magnitudes = selected_magnitudes[valid_mask]
    valid_weights = selected_weights[valid_mask]
    if (valid_magnitudes.size == 0):
        return 0.0

    flux_ratios = 10.0 ** (-0.4 * (valid_magnitudes - target_magnitude))
    weighted_flux_ratios = flux_ratios * valid_weights
    return float(weighted_flux_ratios[np.isfinite(weighted_flux_ratios)].sum() * 100.0)


def flux_fraction_by_band(
    target_index: int,
    contaminant_indices: np.ndarray,
    selected_mask: np.ndarray,
    magnitude_arrays: dict[str, np.ndarray],
    weights: np.ndarray,
) -> dict[str, float]:
    """Compute flux contamination metrics for every requested magnitude band."""
    metrics: dict[str, float] = {}
    for band, magnitudes in magnitude_arrays.items():
        target_magnitude = float(magnitudes[target_index])
        contaminant_magnitudes = np.asarray(magnitudes[contaminant_indices], dtype=np.float64)
        metrics[band] = round(
            calculate_flux_fraction_extra(
                target_magnitude,
                contaminant_magnitudes,
                selected_mask,
                weights,
            ),
            2,
        )
    return metrics


def build_contaminant_records(
    contaminant_indices: np.ndarray,
    contaminant_magnitudes: np.ndarray,
    contaminant_separations: np.ndarray,
    selected_mask: np.ndarray,
    ra: np.ndarray,
    dec: np.ndarray,
    real_ids_int: np.ndarray,
    internal_to_special_name: dict[int, str],
    aperture_location: str | None = None,
    magnitude_arrays: dict[str, np.ndarray] | None = None,
) -> list[dict]:
    """Build public contaminant records from selected catalogue positions."""
    contaminants: list[dict] = []

    for local_index in np.flatnonzero(selected_mask):
        catalogue_index = int(contaminant_indices[local_index])
        magnitude = float(contaminant_magnitudes[local_index])
        record = Contaminant(
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
        if (aperture_location is not None):
            record["aperture_location"] = aperture_location
        if (magnitude_arrays):
            record["magnitudes_by_band"] = {
                band: (float(values[catalogue_index]) if np.isfinite(values[catalogue_index]) else None)
                for band, values in magnitude_arrays.items()
            }
        contaminants.append(record)

    return contaminants


def make_influence_neighbor_provider(
    ra: np.ndarray,
    dec: np.ndarray,
    influence_radius_arcsec: float,
) -> Callable[[int], np.ndarray]:
    """Return a per-target neighbour search out to a query-time influence radius.

    Neighbours are recomputed directly against the full catalogue positions for each
    requested target, so a query ``influence_radius_arcsec`` may exceed the index
    build radius without rebuilding the index. Only the queried targets pay this cost;
    the rest of the catalogue is never re-indexed.
    """
    ra_all = np.asarray(ra, dtype=np.float64)
    dec_all = np.asarray(dec, dtype=np.float64)

    def provider(internal_target: int) -> np.ndarray:
        target_index = internal_target - 1
        separations = separation_arcsec(float(ra_all[target_index]), float(dec_all[target_index]), ra_all, dec_all)
        within = np.flatnonzero(separations <= influence_radius_arcsec)
        within = within[within != target_index]
        return (within + 1).astype(np.int64)

    return provider


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
    contamination_model: ContaminationModelConfig | None = None,
    magnitude_arrays: dict[str, np.ndarray] | None = None,
    influence_radius_arcsec: float | None = None,
    bandpass_status_codes: np.ndarray | None = None,
    bandpass_output_band: str | None = None,
    bandpass_profile_name: str | None = None,
    neighbor_provider: Callable[[int], np.ndarray] | None = None,
) -> dict | None:
    """Evaluate one target while keeping numerical work separate from loop orchestration.

    When ``neighbor_provider`` is supplied, the target's neighbours are recomputed
    from the catalogue out to the influence radius instead of being read from the
    pre-built index, so the query is not capped at the index build radius.
    """
    contamination_model = contamination_model or ContaminationModelConfig()
    magnitude_arrays = magnitude_arrays or {}
    # A PSF-derived influence radius may fall below the aperture: a narrow PSF stops
    # contributing leakage well inside a wide extraction circle. Only the aperture
    # itself bounds the selected contaminants.
    influence_radius_arcsec = field_of_view_arcsec if influence_radius_arcsec is None else influence_radius_arcsec
    number_of_sources = ra.shape[0]
    if (internal_target < 1 or internal_target > number_of_sources):
        logger.warning("internal_target %s out of range; skipping.", internal_target)
        return None

    target_index = internal_target - 1
    bandpass_status = (
        None if bandpass_status_codes is None else transform_status_name(bandpass_status_codes, target_index)
    )
    target_magnitudes_by_band = {
        band: (float(values[target_index]) if np.isfinite(values[target_index]) else None)
        for band, values in magnitude_arrays.items()
    }
    target_ra = float(ra[target_index])
    target_dec = float(dec[target_index])
    target_magnitude = float(gmag[target_index]) if (gmag is not None) else np.nan
    source_id = source_id_from_internal_id(internal_target, real_ids_int, internal_to_special_name)

    if (neighbor_provider is not None):
        neighbor_internal_ids = np.asarray(neighbor_provider(internal_target), dtype=np.int64)
        stored_separations: np.ndarray | None = None
    else:
        start = int(offsets[target_index])
        end = int(offsets[target_index + 1])
        neighbor_internal_ids = np.asarray(neighbors_mm[start:end], dtype=np.int64)
        stored_separations = (
            None if (neighbor_separations_mm is None)
            else np.asarray(neighbor_separations_mm[start:end], dtype=np.float64)
        )

    if (neighbor_internal_ids.size == 0):
        return empty_target_result(
            source_id,
            target_ra,
            target_dec,
            target_magnitude,
            contamination_model,
            list(magnitude_arrays),
            bandpass_output_band,
            bandpass_profile_name,
            bandpass_status,
            target_magnitudes_by_band,
            aperture_radius_arcsec=field_of_view_arcsec,
        )

    candidate_indices = neighbor_internal_ids - 1
    valid_mask = (candidate_indices >= 0) & (candidate_indices < number_of_sources)
    contaminant_indices = candidate_indices[valid_mask]
    if (contaminant_indices.size == 0):
        return empty_target_result(
            source_id,
            target_ra,
            target_dec,
            target_magnitude,
            contamination_model,
            list(magnitude_arrays),
            bandpass_output_band,
            bandpass_profile_name,
            bandpass_status,
            target_magnitudes_by_band,
            aperture_radius_arcsec=field_of_view_arcsec,
        )

    contaminant_ra = ra[contaminant_indices]
    contaminant_dec = dec[contaminant_indices]
    if (gmag is None):
        contaminant_magnitudes = np.full(contaminant_indices.shape, np.nan, dtype=np.float64)
    else:
        contaminant_magnitudes = np.asarray(gmag[contaminant_indices], dtype=np.float64)

    if (stored_separations is None):
        contaminant_separations = separation_arcsec(
            target_ra,
            target_dec,
            contaminant_ra,
            contaminant_dec,
        )
    else:
        contaminant_separations = stored_separations[valid_mask]
    inside_field_of_view = contaminant_separations <= field_of_view_arcsec
    inside_influence_radius = contaminant_separations <= influence_radius_arcsec
    outside_aperture = inside_influence_radius & ~inside_field_of_view
    magnitude_selected = (contaminant_magnitudes - target_magnitude) <= delta_mag
    selected_mask = inside_field_of_view & magnitude_selected
    outside_selected_mask = outside_aperture & magnitude_selected
    weights = contamination_weights(
        contaminant_separations,
        contamination_model,
        field_of_view_arcsec,
    )
    psf_metrics = psf_aperture_metrics(
        target_magnitude,
        contaminant_magnitudes,
        selected_mask,
        contaminant_separations,
        contamination_model,
        field_of_view_arcsec,
    )
    flux_fraction_selected = calculate_flux_fraction_extra(
        target_magnitude,
        contaminant_magnitudes,
        selected_mask,
        weights,
    )
    flux_fraction_all_neighbors = calculate_flux_fraction_extra(
        target_magnitude,
        contaminant_magnitudes,
        inside_field_of_view,
        weights,
    )
    flux_fraction_outside_aperture = calculate_flux_fraction_extra(
        target_magnitude,
        contaminant_magnitudes,
        outside_aperture,
        weights,
    )
    flux_fraction_total_weighted = calculate_flux_fraction_extra(
        target_magnitude,
        contaminant_magnitudes,
        inside_influence_radius,
        weights,
    )
    selected_by_band = flux_fraction_by_band(
        target_index,
        contaminant_indices,
        selected_mask,
        magnitude_arrays,
        weights,
    )
    all_neighbors_by_band = flux_fraction_by_band(
        target_index,
        contaminant_indices,
        inside_field_of_view,
        magnitude_arrays,
        weights,
    )
    outside_by_band = flux_fraction_by_band(
        target_index,
        contaminant_indices,
        outside_aperture,
        magnitude_arrays,
        weights,
    )
    total_weighted_by_band = flux_fraction_by_band(
        target_index,
        contaminant_indices,
        inside_influence_radius,
        magnitude_arrays,
        weights,
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
        "inside",
        magnitude_arrays,
    )
    outside_contaminants = build_contaminant_records(
        contaminant_indices,
        contaminant_magnitudes,
        contaminant_separations,
        outside_selected_mask,
        ra,
        dec,
        real_ids_int,
        internal_to_special_name,
        "outside",
        magnitude_arrays,
    )

    result = TargetResult(
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
    result["contamination_model"] = contamination_model.mode
    result["flux_fraction_selected_by_band"] = selected_by_band
    result["flux_fraction_all_neighbors_by_band"] = all_neighbors_by_band
    result["flux_fraction_inside_aperture"] = round(flux_fraction_all_neighbors, 2)
    result["flux_fraction_outside_aperture"] = round(flux_fraction_outside_aperture, 2)
    result["flux_fraction_total_weighted"] = round(flux_fraction_total_weighted, 2)
    result["flux_fraction_outside_aperture_by_band"] = outside_by_band
    result["flux_fraction_total_weighted_by_band"] = total_weighted_by_band
    result["num_neighbors_in_influence_radius"] = int(np.count_nonzero(inside_influence_radius))
    result["num_neighbors_outside_aperture"] = int(np.count_nonzero(outside_aperture))
    result["num_contaminants_outside_aperture"] = len(outside_contaminants)
    result["outside_aperture_contaminants"] = outside_contaminants
    result["bandpass_transformed_band"] = bandpass_output_band
    result["bandpass_transform_profile"] = bandpass_profile_name
    result["bandpass_transform_status"] = bandpass_status
    result["psf_metrics"] = psf_metrics
    result["target_magnitudes_by_band"] = target_magnitudes_by_band
    result["flux_fraction_selected_transformed"] = (
        None if bandpass_output_band is None else selected_by_band.get(bandpass_output_band)
    )
    result["flux_fraction_all_neighbors_transformed"] = (
        None if bandpass_output_band is None else all_neighbors_by_band.get(bandpass_output_band)
    )
    result["flux_fraction_outside_aperture_transformed"] = (
        None if bandpass_output_band is None else outside_by_band.get(bandpass_output_band)
    )
    result["flux_fraction_total_weighted_transformed"] = (
        None if bandpass_output_band is None else total_weighted_by_band.get(bandpass_output_band)
    )
    return result


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
    contamination_model: ContaminationModelConfig | None = None,
    magnitude_arrays: dict[str, np.ndarray] | None = None,
    influence_radius_arcsec: float | None = None,
    bandpass_status_codes: np.ndarray | None = None,
    bandpass_output_band: str | None = None,
    bandpass_profile_name: str | None = None,
    neighbor_provider: Callable[[int], np.ndarray] | None = None,
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
            contamination_model,
            magnitude_arrays,
            influence_radius_arcsec,
            bandpass_status_codes,
            bandpass_output_band,
            bandpass_profile_name,
            neighbor_provider,
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
    bandpass_profile: BandpassTransformProfile | None = None,
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
                "Sources are selected within the configured circular aperture and optional influence radius "
                "and delta-magnitude limit; flux_fraction_selected is computed from catalogue "
                "magnitude ratios for the selected sources, while flux_fraction_all_neighbors "
                "uses every valid neighbour inside the aperture. Weighted models can additionally "
                "estimate radial leakage from sources between the aperture and influence radii."
            ),
            "not_included": [
                "spatially varying or asymmetric instrumental PSF convolution",
                "detector pixel response",
                "full SED integration or synthetic photometry beyond an optional empirical colour transformation",
                "scattered-light or diffraction features not represented by the selected radial model",
            ],
        },
        "bandpass_transform": None if bandpass_profile is None else bandpass_profile.metadata(),
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

    bandpass_profile = None
    if (config_query.bandpass_transform_file is not None):
        bandpass_profile = load_bandpass_profile(config_query.bandpass_transform_file)
        if (bandpass_profile.output_band in manifest_magnitude_bands(runtime_plan.manifest)):
            raise ValueError(
                f"Bandpass transformation output_band {bandpass_profile.output_band} conflicts with "
                "a catalogue band already stored in the index. Choose a distinct mission-band name."
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

    requested_bands = resolve_requested_bands(config_query.contamination_bands, runtime_plan.manifest)
    bands_to_load = list(requested_bands)
    if (bandpass_profile is not None):
        resolve_requested_bands(list(bandpass_profile.required_bands), runtime_plan.manifest)
        bands_to_load.extend(band for band in bandpass_profile.required_bands if band not in bands_to_load)
    loaded_magnitude_arrays = load_magnitude_arrays(paths.root, runtime_plan.manifest, bands_to_load)
    magnitude_arrays = {band: loaded_magnitude_arrays[band] for band in requested_bands}
    bandpass_status_codes = None
    if (bandpass_profile is not None):
        transformed = transform_magnitudes(bandpass_profile, loaded_magnitude_arrays)
        magnitude_arrays[bandpass_profile.output_band] = transformed.magnitudes
        bandpass_status_codes = transformed.status_codes
    
    # For targets whose influence radius exceeds the index build radius, recompute
    # their neighbours directly from the catalogue so the query is not capped by the
    # build radius. Only the requested targets are recomputed.
    neighbor_provider = None
    if (config_query.effective_influence_radius_arcsec > runtime_plan.manifest.max_radius_arcsec):
        logger.info(
            "Recomputing neighbours out to the influence radius (%.3f arcsec) for %d target(s)...",
            config_query.effective_influence_radius_arcsec,
            len(targets_internal),
        )
        neighbor_provider = make_influence_neighbor_provider(
            ra,
            dec,
            config_query.effective_influence_radius_arcsec,
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
        contamination_model=config_query.contamination_model,
        magnitude_arrays=magnitude_arrays,
        influence_radius_arcsec=config_query.effective_influence_radius_arcsec,
        bandpass_status_codes=bandpass_status_codes,
        bandpass_output_band=None if bandpass_profile is None else bandpass_profile.output_band,
        bandpass_profile_name=None if bandpass_profile is None else bandpass_profile.name,
        neighbor_provider=neighbor_provider,
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
            bandpass_profile,
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
