#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""
build_neighbors_index.py  (streaming + low-memory + resumable + optimized)

Purpose
-------
Build a neighbor index for each star within a maximum angular radius.

The index is stored in a CSR-like layout plus a compact ID mapping:

    Geometry / neighbor index
    -------------------------
    - source_ids.npy
        int64, shape (N,)
        Internal "internal_id" for each catalog row, in catalog order.
        Values are 1..N and are used everywhere as primary keys.

    - offsets.npy
        int64, shape (N+1,)
        CSR-style offsets. Neighbors for star i (0-based row index) are in:
            neighbors_ids[offsets[i] : offsets[i+1]]

    - neighbors_ids.bin
        int64, binary file, length = total number of neighbor entries.
        For each star, contains the internal_id of all its neighbors, concatenated.

    - neighbors_seps.bin (optional)
        float64, binary file, same length as neighbors_ids.bin.
        Angular separation (arcsec) between the star and each neighbor, in the
        same order as neighbors_ids.bin. Only written if calculate_separations is True.

    Catalog / ID mapping
    --------------------
    - master_catalog.parquet
        Parquet table with at least:
            ['source_id', 'ra', 'dec', 'phot_g_mean_mag', 'internal_id']
        Ordered identically to source_ids.npy (1 ↔ row 0, 2 ↔ row 1, ...).

    - ra.npy, dec.npy, phot_g_mean_mag.npy
        float64 NumPy arrays, shape (N,), storing the numeric columns in catalog
        order (aligned with internal_id).

    - real_ids_int.npy
        int64 NumPy array, shape (N,).
        Stores the *real* external source ID if it is purely numeric (e.g. Gaia
        source_id). For rows where the real ID is not a pure integer (e.g.
        "HD 216608A"), the value is -1.

    - special_ids.npz
        Compressed NPZ file with two arrays:
            * internal_ids : int64[:]  -> internal_id values for rows with non-numeric IDs
            * names    : unicode[:] -> the original string IDs for those rows
        Only a tiny subset of the catalog (e.g. ~2000 rows) will be stored here.

    - index_manifest.json
        Versioned completion metadata tying the index to its catalogue, radius,
        counts, and safe on-disk format.

Key ideas
---------
    - Convert RA/Dec to 3D unit vectors and use cKDTree with chord distance
      for angular neighbor searches on the sphere.
    - Process sources in chunks to keep memory usage under control.
    - Stream neighbors to disk with small Python buffers and periodic flushes.
    - Save an atomic, input-bound checkpoint with CSR offsets and total neighbor
      count to resume after interruptions without restarting from scratch.

Inputs (from config_and_run_new)
--------------------------------
    - input_catalog (str)
        Path to input CSV catalog.

    - out_dir (str)
        Directory where all outputs and checkpoints will be written.

    - use_dask (bool)
        If True, load the CSV using Dask (for very large files).
        If False, load with pandas.read_csv.

    - calculate_separations (bool)
        If True, also compute and store angular separations in neighbors_seps.bin.

    - max_radius_arcsec (float)
        Search radius for neighbors, in arcseconds.

    - chunk_size (int)
        Number of rows (stars) processed per block when querying the KDTree.

    - buffer_flush_interval (int)
        Number of blocks after which buffered neighbor arrays are flushed to disk
        and a checkpoint is written.

    - source_id_column, ra_column, dec_column, phot_g_mean_mag_column (str)
        Column names to load from the input CSV. The default names are Gaia-like:
            source_id, ra, dec, phot_g_mean_mag.
        Change these in config.yaml/GUI if your CSV uses different headers.

Output
------
All files listed above are created under out_dir.
"""

import csv
import re
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Iterator

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree  # pyright: ignore[reportAttributeAccessIssue]
from tqdm import tqdm
from numpy.typing import NDArray

from .index_manifest import (
    INDEX_MANIFEST_FILENAME,
    IndexManifest,
    atomic_save_npy,
    atomic_save_npz,
    build_signature,
    load_index_manifest,
    sha256_file,
    validate_index_structure,
    write_index_manifest,
)
from .logger_setup import USE_COLOR, get_logger
from .load_config import BuildConfig, load_config
from .path_policy import ensure_directory, index_paths
from .pipeline_display import ActivityBar, tqdm_options


logger = get_logger(__name__)

# Bold on / bold off. These compose with the yellow the log formatter already wraps
# a warning in (they change intensity, not colour), so emphasis stays yellow.
_BOLD = "\033[1m"
_BOLD_OFF = "\033[22m"


def _emphasis(text: str) -> str:
    """Return ``text`` in bold when the terminal supports colour, else unchanged."""
    return f"{_BOLD}{text}{_BOLD_OFF}" if USE_COLOR else text


def _plural_rows(count: int) -> str:
    """Return 'row' or 'rows' agreeing with ``count``."""
    return "row" if (count == 1) else "rows"


def _dropped_rows_message(
    reason: str,
    per_field_counts: dict[str, int],
    catalog_row_numbers: np.ndarray,
) -> str:
    """Build a specific, emphasised warning naming what was dropped and where.

    ``per_field_counts`` maps a human field/check label to how many rows it
    affected (rows can fail more than one check). ``catalog_row_numbers`` are the
    1-based data-row numbers in the original catalog (header excluded), so a user
    can locate the offending rows regardless of any earlier cleaning.
    """
    dropped_rows = int(catalog_row_numbers.size)
    lines = [f"Dropped {_emphasis(str(dropped_rows))} catalog {_plural_rows(dropped_rows)} with {reason}:"]
    for label, count in sorted(per_field_counts.items(), key=lambda item: item[1], reverse=True):
        lines.append(f"  - {_emphasis(label)}: {_emphasis(str(count))} {_plural_rows(count)}")

    rows = catalog_row_numbers.tolist()
    preview = ", ".join(str(row) for row in rows[:10])
    remaining = len(rows) - 10
    if (remaining > 0):
        preview += f", ... (+{remaining} more)"
    lines.append(f"  Affected catalog rows (header excluded): {_emphasis(preview)}")
    lines.append("Fix or remove these rows in the catalog CSV, then rebuild the index.")
    return "\n".join(lines)


@contextmanager
def exclusive_build_lock(out_dir: str | Path) -> Iterator[None]:
    """Hold a cross-platform advisory lock for one index output directory."""
    lock_path = Path(out_dir) / ".photo-cat-build.lock"
    lock_file = lock_path.open("a+b")
    if (lock_file.seek(0, os.SEEK_END) == 0):
        lock_file.write(b"\0")
        lock_file.flush()
    lock_file.seek(0)

    try:
        if (sys.platform == "win32"):
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        lock_file.close()
        raise RuntimeError(
            f"Another PHOTO-CAT build is already using this output directory: {out_dir}"
        ) from error

    try:
        yield
    finally:
        lock_file.seek(0)
        if (sys.platform == "win32"):
            import msvcrt

            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


def read_csv_header(input_catalog: str) -> list[str]:
    with open(input_catalog, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            raise ValueError(f"Catalog CSV is empty: {input_catalog}")

    return [str(column).strip() for column in header]


def validate_required_columns(input_catalog: str, required_columns: list[str]) -> None:
    header = read_csv_header(input_catalog)
    missing_columns = [column for column in required_columns if column not in header]

    if (not missing_columns):
        return

    case_matches = []
    for missing_column in missing_columns:
        matches = [column for column in header if (column.lower() == missing_column.lower())]
        for match in matches:
            case_matches.append(f'configured "{missing_column}", CSV has "{match}"')

    message = (
        "Catalog CSV column mismatch.\n\n"
        "The configured catalog column names were not found in the CSV header.\n"
        "Column names are case-sensitive: ra is different from RA, "
        "and phot_g_mean_mag is different from PHOT_G_MEAN_MAG.\n\n"
        "Missing configured columns:\n"
        + "\n".join(f"- {column}" for column in missing_columns)
    )

    if (case_matches):
        message += (
            "\n\nPossible uppercase/lowercase mismatch found:\n"
            + "\n".join(f"- {case_match}" for case_match in case_matches)
        )

    message += (
        f"\n\nCSV file:\n{input_catalog}\n\n"
        "Available CSV header columns:\n"
        + "\n".join(f"- {column}" for column in header[:80])
    )

    if (len(header) > 80):
        message += f"\n- ... and {len(header) - 80} more"

    raise ValueError(message)


def load_star_dataframe(
    input_catalog: str,
    use_dask: bool,
    source_id_column: str = "source_id",
    ra_column: str = "ra",
    dec_column: str = "dec",
    phot_g_mean_mag_column: str = "phot_g_mean_mag",
    magnitude_columns: dict[str, str] | None = None,
    stellar_parameter_columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Load the star catalog from CSV using pandas or Dask, keep only valid rows,
    and assign an internal internal_id for each row.

    Parameters
    ----------
    input_catalog : str
        Path to the CSV file containing the star catalog.

    use_dask : bool
        If True, load via Dask (good for huge CSVs).
        If False, load via pandas.

    source_id_column, ra_column, dec_column, phot_g_mean_mag_column : str
        CSV column names used for source ID, right ascension, declination, and magnitude.
        The loaded DataFrame is normalized internally to source_id, ra, dec, phot_g_mean_mag.

    Returns
    -------
    final_star_dataframe : pandas.DataFrame
        Cleaned DataFrame with:
            - 'source_id' as string
            - 'ra', 'dec', and optionally 'phot_g_mean_mag'
            - 'internal_id' as int64, running from 1..N
    """
    logger.info(f"Loading catalog: {input_catalog}")
    logger.info(f"Using {'Dask' if use_dask else 'Pandas'}...")

    magnitude_columns = {"gaia_g": phot_g_mean_mag_column, **(magnitude_columns or {})}
    stellar_parameter_columns = stellar_parameter_columns or {}
    usecolumns = [
        source_id_column,
        ra_column,
        dec_column,
        phot_g_mean_mag_column,
    ]
    for column in magnitude_columns.values():
        if (column not in usecolumns):
            usecolumns.append(column)
    for column in stellar_parameter_columns.values():
        if (column not in usecolumns):
            usecolumns.append(column)

    if (any(column == "" for column in usecolumns)):
        raise ValueError("Catalog column names cannot be empty.")

    if (len(set(usecolumns)) != len(usecolumns)):
        raise ValueError("Catalog Source ID, RA, Dec, and magnitude columns must be different.")

    logger.info("Catalog column mapping:")
    logger.info(f" - source_id: {source_id_column}")
    logger.info(f" - ra: {ra_column}")
    logger.info(f" - dec: {dec_column}")
    logger.info(f" - phot_g_mean_mag: {phot_g_mean_mag_column}")
    if (len(magnitude_columns) > 1):
        for band, column in sorted(magnitude_columns.items()):
            logger.info(f" - magnitude band {band}: {column}")
    for parameter, column in sorted(stellar_parameter_columns.items()):
        logger.info(f" - stellar parameter {parameter}: {column}")

    validate_required_columns(input_catalog, usecolumns)

    if use_dask:
        try:
            import dask.dataframe as dd
        except ImportError as exc:
            raise ImportError(
                "Dask is required when use_dask is true. "
                "Install it with: pip install dask[dataframe]"
            ) from exc

        # Dask lazy load and compute in parallel.
        star_input_catalog = dd.read_csv(
            input_catalog,
            usecols=usecolumns,
            dtype={source_id_column: "object"},
            assume_missing=True
        )
        with ActivityBar("[loading catalog with Dask]"):
            star_dataframe = star_input_catalog.compute()
    else:
        with ActivityBar("[loading catalog with Pandas]"):
            star_dataframe = pd.read_csv(
                input_catalog,
                usecols=usecolumns,
                dtype={source_id_column: "object"}
            )

    star_dataframe = star_dataframe.rename(
        columns={
            source_id_column: "source_id",
            ra_column: "ra",
            dec_column: "dec",
            phot_g_mean_mag_column: "phot_g_mean_mag",
        }
    )

    for band, source_column in magnitude_columns.items():
        safe_band = safe_band_name(band)
        if (source_column == phot_g_mean_mag_column):
            continue
        band_column = f"magnitude_{safe_band}"
        star_dataframe[band_column] = star_dataframe[source_column]

    for parameter, source_column in stellar_parameter_columns.items():
        parameter_column = f"parameter_{safe_band_name(parameter)}"
        star_dataframe[parameter_column] = star_dataframe[source_column]

    logger.info(f"Loaded {len(star_dataframe)} rows.")
    logger.info("Validating and cleaning catalog rows (this can take a while for very large catalogs)...")

    if (len(star_dataframe) == 0):
        raise ValueError(
            "The catalog CSV was read successfully, but it contains no data rows.\n"
            "Add at least one catalog row below the header."
        )

    band_numeric_columns = [
        f"magnitude_{safe_band_name(band)}"
        for band, source_column in magnitude_columns.items()
        if (source_column != phot_g_mean_mag_column)
    ]
    numeric_columns = ["ra", "dec", "phot_g_mean_mag", *band_numeric_columns]
    numeric_errors = []
    for column in numeric_columns:
        star_dataframe[column] = pd.to_numeric(star_dataframe[column], errors="coerce")
        if (star_dataframe[column].isna().all()):
            numeric_errors.append(column)

    if (numeric_errors):
        raise ValueError(
            "Catalog numeric column problem.\n\n"
            "These configured catalog columns were found, but they do not contain usable numeric values:\n"
            + "\n".join(f"- {column}" for column in numeric_errors)
            + "\n\nCheck that RA, Dec, and magnitude columns contain numbers, not text."
        )

    # Atmospheric quantities are optional per row: coerce malformed/missing
    # values to NaN and let the query-time PHOENIX decision tree choose a fallback.
    for parameter in stellar_parameter_columns:
        parameter_column = f"parameter_{safe_band_name(parameter)}"
        star_dataframe[parameter_column] = pd.to_numeric(
            star_dataframe[parameter_column], errors="coerce"
        )

    # Drop rows missing mandatory fields and normalize IDs to strings. The warning
    # names which field failed and where, so a user can find and fix the offending
    # rows instead of guessing.
    mandatory_fields = {
        "source_id": "source_id",
        "ra": "RA (ra)",
        "dec": "Dec (dec)",
        "phot_g_mean_mag": "magnitude (phot_g_mean_mag)",
    }
    # 1-based catalog data-row numbers (header excluded), tracked across both drop
    # stages so warnings can always point at the original CSV rows.
    catalog_row_numbers = np.arange(1, len(star_dataframe) + 1)

    # The pandas stubs type these reductions as returning a scalar rather than the
    # Series they return at runtime, so the .to_numpy() calls below are flagged.
    missing_mask = star_dataframe[list(mandatory_fields)].isna()
    dropped_any = missing_mask.any(axis=1).to_numpy()  # pyright: ignore[reportAttributeAccessIssue]
    dropped_rows = int(dropped_any.sum())
    per_field_missing = {
        label: int(missing_mask[column].to_numpy().sum())  # pyright: ignore[reportAttributeAccessIssue]
        for column, label in mandatory_fields.items()
        if bool(missing_mask[column].to_numpy().any())  # pyright: ignore[reportAttributeAccessIssue]
    }
    final_star_dataframe = star_dataframe.dropna(
        subset=['source_id', 'ra', 'dec', 'phot_g_mean_mag']
    ).reset_index(drop=True)
    rows_after_drop = len(final_star_dataframe)
    # Original row numbers of the survivors, aligned with final_star_dataframe order.
    surviving_row_numbers = catalog_row_numbers[~dropped_any]

    if (dropped_rows > 0):
        logger.warning(
            _dropped_rows_message(
                "missing or non-numeric required fields",
                per_field_missing,
                catalog_row_numbers[dropped_any],
            )
        )

    if (rows_after_drop == 0):
        raise ValueError(
            "No valid catalog rows remain after cleaning.\n\n"
            "Every usable row must have source_id, RA, Dec, and magnitude values."
        )

    final_star_dataframe['source_id'] = final_star_dataframe['source_id'].astype(str)

    ra_values = final_star_dataframe["ra"].to_numpy(dtype=np.float64)
    dec_values = final_star_dataframe["dec"].to_numpy(dtype=np.float64)
    finite_rows = np.isfinite(
        final_star_dataframe[["ra", "dec", "phot_g_mean_mag"]].to_numpy(dtype=np.float64)
    ).all(axis=1)
    ra_in_range = (ra_values >= 0.0) & (ra_values < 360.0)
    dec_in_range = (dec_values >= -90.0) & (dec_values <= 90.0)
    valid_rows = finite_rows & ra_in_range & dec_in_range
    invalid_mask = ~valid_rows
    invalid_coordinate_count = int(invalid_mask.sum())
    if (invalid_coordinate_count):
        # Break the drop down by which check failed, so the fix is obvious.
        per_check_invalid = {
            label: int(mask.sum())
            for label, mask in (
                ("non-finite RA/Dec/magnitude", ~finite_rows),
                ("RA outside [0, 360)", finite_rows & ~ra_in_range),
                ("Dec outside [-90, 90]", finite_rows & ~dec_in_range),
            )
            if bool(mask.any())
        }
        logger.warning(
            _dropped_rows_message(
                "non-finite or out-of-range coordinates or magnitude",
                per_check_invalid,
                surviving_row_numbers[invalid_mask],
            )
        )
        final_star_dataframe = final_star_dataframe.loc[valid_rows].reset_index(drop=True)

    if (final_star_dataframe.empty):
        raise ValueError(
            "No valid catalog rows remain after coordinate validation. "
            "RA must be in [0, 360), Dec in [-90, 90], and magnitudes must be finite."
        )

    duplicate_ids = final_star_dataframe["source_id"].duplicated(keep=False)
    if (duplicate_ids.any()):
        examples = ", ".join(final_star_dataframe.loc[duplicate_ids, "source_id"].unique()[:8])
        raise ValueError(
            "Catalog source_id values must be unique because query targets map to one row. "
            f"Duplicate examples: {examples}"
        )

    with ActivityBar("[validating source IDs]"):
        canonical_ids: list[tuple[str, object]] = []
        for source_id in final_star_dataframe["source_id"]:
            try:
                numeric_id = int(source_id)
            except (TypeError, ValueError):
                canonical_ids.append(("text", source_id))
            else:
                if (0 <= numeric_id <= np.iinfo(np.int64).max):
                    canonical_ids.append(("numeric", numeric_id))
                else:
                    canonical_ids.append(("text", source_id))
        canonical_duplicates = pd.Series(canonical_ids).duplicated(keep=False)
    if (canonical_duplicates.any()):
        examples = ", ".join(final_star_dataframe.loc[canonical_duplicates, "source_id"].unique()[:8])
        raise ValueError(
            "Catalog source_id values must remain unique after numeric normalization. "
            f"Ambiguous examples: {examples}"
        )

    # Assign monotonically increasing internal IDs for internal indexing.
    # These will be used to:
    #   - store neighbors in neighbors_ids.bin
    #   - index RA/Dec/Gmag arrays
    final_star_dataframe['internal_id'] = np.arange(
        1,
        len(final_star_dataframe) + 1,
        dtype=np.int64
    )

    logger.info(f"Final catalog contains {len(final_star_dataframe)} valid rows.\n")
    return final_star_dataframe


def safe_band_name(band: str) -> str:
    """Return a stable filesystem-safe magnitude-band identifier."""
    safe = re.sub(r"[^0-9A-Za-z_]+", "_", str(band).strip().lower()).strip("_")
    if (safe == ""):
        raise ValueError("Magnitude band names cannot be empty.")
    return safe


def magnitude_band_manifest(magnitude_columns: dict[str, str], phot_g_mean_mag_column: str) -> dict[str, dict[str, str]]:
    """Describe persisted magnitude arrays for query-time multi-band metrics."""
    manifest: dict[str, dict[str, str]] = {}
    for band, source_column in magnitude_columns.items():
        safe_band = safe_band_name(band)
        array_file = "phot_g_mean_mag.npy" if (source_column == phot_g_mean_mag_column) else f"magnitude_{safe_band}.npy"
        manifest[band] = {
            "catalog_column": source_column,
            "array_file": array_file,
        }
    return manifest


def stellar_parameter_manifest(stellar_parameter_columns: dict[str, str]) -> dict[str, dict[str, str]]:
    """Describe persisted atmospheric-parameter arrays for SED conversion."""
    return {
        parameter: {
            "catalog_column": source_column,
            "array_file": f"parameter_{safe_band_name(parameter)}.npy",
        }
        for parameter, source_column in stellar_parameter_columns.items()
    }


def convert_ra_dec_to_unit_vectors(
    final_star_dataframe: pd.DataFrame
) -> NDArray[np.float64]:
    """
    Convert celestial coordinates (RA, Dec) to 3D unit vectors on the unit sphere.

    This allows cKDTree to operate in simple Euclidean space and still represent
    angular separations on the sky.

    Parameters
    ----------
    final_star_dataframe : pandas.DataFrame
        Must contain at least 'ra' and 'dec' columns in degrees.

    Returns
    -------
    coords : numpy.ndarray
        Array of shape (N, 3) containing unit vectors [x, y, z] for each star.
    """
    logger.info("Converting RA/Dec to 3D unit vectors...")

    with ActivityBar("[converting coordinates]"):
        ra_rad = np.deg2rad(final_star_dataframe['ra'].values.astype(np.float64))
        dec_rad = np.deg2rad(final_star_dataframe['dec'].values.astype(np.float64))

        x = np.cos(dec_rad) * np.cos(ra_rad)
        y = np.cos(dec_rad) * np.sin(ra_rad)
        z = np.sin(dec_rad)

        # Stack into an (N, 3) array.
        coords = np.hstack([
            x[:, None],
            y[:, None],
            z[:, None]
        ]).astype(np.float64)

    logger.info(f"Converted {len(coords)} coordinates to 3D unit vectors.\n")
    return coords


def compute_chord_radius(max_radius_arcsec: float) -> np.float64:
    """
    Convert a maximum angular search radius (in arcseconds) to a chordal
    distance in 3D unit-vector space.

    For two unit vectors u, v separated by an angle θ (in radians):
        chord_distance = |u - v| = 2 * sin(θ / 2)

    Parameters
    ----------
    max_radius_arcsec : float
        Angular search radius in arcseconds.

    Returns
    -------
    chord_radius : numpy.float64
        Chordal distance corresponding to max_radius_arcsec.
    """
    logger.info("Computing chordal radius from angular separation...")

    max_radius_rad = np.deg2rad(max_radius_arcsec / 3600.0)
    chord_radius = 2.0 * np.sin(max_radius_rad / 2.0)

    logger.info(f"Chordal radius: {chord_radius:.6e}\n")
    return chord_radius


def build_or_load_kdtree(
    coords: np.ndarray,
) -> cKDTree:
    """
    Build a cKDTree without deserializing executable pickle payloads.

    Parameters
    ----------
    coords : numpy.ndarray
        Unit vectors with shape (N, 3).

    Returns
    -------
    coordinate_tree : scipy.spatial.cKDTree
        KDTree instance ready for query_ball_point searches.
    """
    logger.info("Building cKDTree in memory...")
    with ActivityBar("[building KDTree]"):
        coordinate_tree = cKDTree(coords)

    return coordinate_tree


def resume_from_checkpoint(
    checkpoint_path: str,
    number_of_stars_in_dataframe: int,
    expected_build_signature: str,
) -> tuple[int, np.ndarray, int]:
    """
    Load or initialize CSR offsets and progress for a resumable run.

    The checkpoint stores:
      - start_index : next catalog index (0-based) to process
      - offsets     : int64 (N+1,) CSR offsets array
      - total       : total number of neighbor entries written so far

    Parameters
    ----------
    checkpoint_path : str
        Path to the .npz checkpoint file.

    number_of_stars_in_dataframe : int
        Total number of stars N in the catalog.

    Returns
    -------
    checkpoint_index : int
        Index in [0, N) to resume processing from.

    offsets : numpy.ndarray
        CSR offsets array of length N+1. If no checkpoint existed, it is
        freshly allocated and initialized with offsets[0] = 0.

    checkpoint_total : int
        Total number of neighbor entries already written to disk.
    """
    checkpoint_index = 0

    if os.path.exists(checkpoint_path):
        try:
            with np.load(checkpoint_path, allow_pickle=False) as checkpoint:
                checkpoint_signature = str(checkpoint["build_signature"].item())
                checkpoint_index = int(checkpoint["start_index"])
                offsets = checkpoint["offsets"].astype(np.int64, copy=True)
                checkpoint_total = int(checkpoint["total"])
        except (KeyError, OSError, ValueError) as error:
            raise ValueError(
                f"Resume checkpoint is malformed: {checkpoint_path}. "
                "Remove it to start a clean rebuild."
            ) from error

        if (checkpoint_signature != expected_build_signature):
            logger.warning("Ignoring a stale checkpoint created from different build inputs.")
            checkpoint_index = 0
            offsets = np.empty(number_of_stars_in_dataframe + 1, dtype=np.int64)
            offsets[0] = 0
            checkpoint_total = 0
        elif (
            checkpoint_index < 0
            or checkpoint_index > number_of_stars_in_dataframe
            or offsets.shape != (number_of_stars_in_dataframe + 1,)
            or checkpoint_total < 0
            or int(offsets[checkpoint_index]) != checkpoint_total
        ):
            raise ValueError(
                "Resume checkpoint does not match its catalog dimensions or binary progress. "
                "Remove it to start a clean rebuild."
            )
        else:
            if checkpoint_index == number_of_stars_in_dataframe:
                logger.info("Checkpoint contains all neighbour blocks; finalizing index outputs.")
            else:
                logger.info(f"[RESUME] Found checkpoint. Resuming from index {checkpoint_index}.")
    else:
        # Fresh run: allocate offsets (N+1) and start at 0 neighbors.
        offsets = np.empty(number_of_stars_in_dataframe + 1, dtype=np.int64)
        offsets[0] = 0
        checkpoint_total = 0
        logger.info("No checkpoint found. Starting from the beginning.\n")

    return checkpoint_index, offsets, checkpoint_total


def neighbor_indices_without_self(neighbor_indices: list[int], target_index: int) -> NDArray[np.int64]:
    """Convert KDTree results to int64 indices while removing the target itself."""
    if (not neighbor_indices):
        return np.empty(0, dtype=np.int64)

    indices = np.asarray(neighbor_indices, dtype=np.int64)
    return indices[indices != target_index]


def calculate_neighbor_separations_arcsec(
    coords: NDArray[np.float64],
    target_index: int,
    neighbor_indices: NDArray[np.int64],
) -> NDArray[np.float64]:
    """Calculate vectorized angular separations for one target's neighbours."""
    target_vector = coords[target_index]
    neighbor_vectors = coords[neighbor_indices]
    dot_product = np.einsum("ij,j->i", neighbor_vectors, target_vector)
    dot_product = np.clip(dot_product, -1.0, 1.0)
    return (np.rad2deg(np.arccos(dot_product)) * 3600.0).astype(np.float64)


def flush_neighbor_buffers(
    neighbors_buffer: list[NDArray[np.int64]],
    separations_buffer: list[NDArray[np.float64]],
    neighbors_file: BinaryIO,
    separations_file: BinaryIO | None,
    calculate_separations: bool,
) -> None:
    """Write accumulated index buffers to disk and clear them in place."""
    if (neighbors_buffer):
        np.concatenate(neighbors_buffer).tofile(neighbors_file)
        neighbors_buffer.clear()

    if (calculate_separations and separations_buffer and separations_file is not None):
        np.concatenate(separations_buffer).tofile(separations_file)
        separations_buffer.clear()


def reconcile_resume_file(
    temporary_path: str,
    final_path: str,
    expected_size: int,
    *,
    checkpoint_complete: bool,
) -> None:
    """Truncate uncheckpointed bytes or recover a file already finalized before a crash."""
    temporary = Path(temporary_path)
    final = Path(final_path)
    if (not temporary.exists()):
        if (checkpoint_complete and final.is_file() and final.stat().st_size == expected_size):
            return
        raise ValueError(
            f"Resume data is missing: {temporary}. Remove resume_checkpoint.npz to rebuild cleanly."
        )

    actual_size = temporary.stat().st_size
    if (actual_size < expected_size):
        raise ValueError(
            f"Resume data is truncated: {temporary}. Remove resume_checkpoint.npz to rebuild cleanly."
        )
    if (actual_size > expected_size):
        logger.warning("Discarding %s uncheckpointed byte(s) from %s.", actual_size - expected_size, temporary)
        with temporary.open("r+b") as file:
            file.truncate(expected_size)


def write_checkpoint(
    checkpoint_path: str,
    start_index: int,
    offsets: NDArray[np.int64],
    total: int,
    build_signature_value: str,
) -> None:
    """Persist resumable CSR progress after complete output blocks."""
    atomic_save_npz(
        checkpoint_path,
        start_index=np.array(start_index, dtype=np.int64),
        offsets=offsets,
        total=np.array(total, dtype=np.int64),
        build_signature=np.array(build_signature_value),
    )


def calculate_contaminants(
    checkpoint_index: int,
    number_of_stars_in_dataframe: int,
    chunk_size: int,
    coords: NDArray[np.float64],
    chord_radius: np.float64,
    coordinate_tree: cKDTree,
    offsets: NDArray[np.int64],
    checkpoint_total: int,
    final_star_dataframe: pd.DataFrame,
    neighbors_file: BinaryIO,
    separations_file: BinaryIO | None,
    buffer_flush_interval: int,
    calculate_separations: bool,
    checkpoint_path: str,
    build_signature_value: str,
) -> tuple[pd.DataFrame, NDArray[np.int64], int]:
    """Build the resumable CSR neighbour index without mixing I/O helper responsibilities."""
    logger.info("Building neighbor index (resumable mode)...")

    progress = tqdm(
        total=number_of_stars_in_dataframe,
        initial=checkpoint_index,
        unit="stars",
        **tqdm_options("Building index"),
    )
    internal_ids = final_star_dataframe["internal_id"].to_numpy(dtype=np.int64)
    neighbors_buffer: list[NDArray[np.int64]] = []
    separations_buffer: list[NDArray[np.float64]] = []
    blocks_since_flush = 0

    try:
        for start in range(checkpoint_index, number_of_stars_in_dataframe, chunk_size):
            end = min(number_of_stars_in_dataframe, start + chunk_size)
            neighbor_lists = coordinate_tree.query_ball_point(
                coords[start:end],
                r=chord_radius,
                workers=-1,
            )

            for local_index, neighbor_list in enumerate(neighbor_lists):
                target_index = start + local_index
                neighbor_indices = neighbor_indices_without_self(neighbor_list, target_index)

                if (neighbor_indices.size == 0):
                    offsets[target_index + 1] = checkpoint_total
                    continue

                contaminant_ids = internal_ids[neighbor_indices]
                neighbors_buffer.append(contaminant_ids)

                if (calculate_separations):
                    separations_buffer.append(
                        calculate_neighbor_separations_arcsec(coords, target_index, neighbor_indices)
                    )

                checkpoint_total += contaminant_ids.size
                offsets[target_index + 1] = checkpoint_total

            blocks_since_flush += 1
            progress.update(end - start)

            if (blocks_since_flush >= buffer_flush_interval):
                flush_neighbor_buffers(
                    neighbors_buffer,
                    separations_buffer,
                    neighbors_file,
                    separations_file,
                    calculate_separations,
                )
                neighbors_file.flush()
                os.fsync(neighbors_file.fileno())
                if (separations_file is not None):
                    separations_file.flush()
                    os.fsync(separations_file.fileno())
                write_checkpoint(
                    checkpoint_path,
                    end,
                    offsets,
                    checkpoint_total,
                    build_signature_value,
                )
                blocks_since_flush = 0

        flush_neighbor_buffers(
            neighbors_buffer,
            separations_buffer,
            neighbors_file,
            separations_file,
            calculate_separations,
        )
        neighbors_file.flush()
        os.fsync(neighbors_file.fileno())
        if (separations_file is not None):
            separations_file.flush()
            os.fsync(separations_file.fileno())
        write_checkpoint(
            checkpoint_path,
            number_of_stars_in_dataframe,
            offsets,
            checkpoint_total,
            build_signature_value,
        )
    finally:
        neighbors_file.close()
        if (separations_file is not None):
            separations_file.close()
        progress.close()

    return final_star_dataframe, offsets, checkpoint_total

def save_final_outputs(
    out_dir: str,
    final_star_dataframe: pd.DataFrame,
    offsets: np.ndarray,
    neighbors_tmp_path: str,
    separations_tmp_path: str | None,
    calculate_separations: bool,
    *,
    build_signature_value: str,
    catalog_sha256: str,
    max_radius_arcsec: float,
    total_neighbors: int,
    magnitude_columns: dict[str, str],
    phot_g_mean_mag_column: str,
    stellar_parameter_columns: dict[str, str] | None = None,
) -> str:
    """
    Finalize temporary files atomically, build compact ID mapping arrays,
    and write numeric columns to standalone NumPy arrays.

    Parameters
    ----------
    out_dir : str
        Output directory.

    final_star_dataframe : pandas.DataFrame
        Full catalog (already cleaned) with 'source_id', 'ra', 'dec',
        optionally 'phot_g_mean_mag', and 'internal_id'.

    offsets : numpy.ndarray
        CSR offsets array (N+1,).

    neighbors_tmp_path : str
        Path to neighbors_ids.tmp.

    separations_tmp_path : str or None
        Path to neighbors_seps.tmp (if separations were computed).

    calculate_separations : bool
        Whether neighbors_seps.bin should be finalized.

    Returns
    -------
    master_path : str
        Path to master_catalog.parquet.
    """
    manifest_path = Path(out_dir) / INDEX_MANIFEST_FILENAME
    manifest_path.unlink(missing_ok=True)

    # Rename temporary neighbor files to their final names. If a prior finalization
    # crashed after this rename, retain the already-complete binary and rewrite the
    # remaining derived files before publishing a new manifest.
    neighbors_final_path = Path(out_dir) / "neighbors_ids.bin"
    if (Path(neighbors_tmp_path).exists()):
        os.replace(neighbors_tmp_path, neighbors_final_path)
    elif (
        not neighbors_final_path.is_file()
        or neighbors_final_path.stat().st_size != total_neighbors * np.dtype(np.int64).itemsize
    ):
        raise ValueError("Completed neighbour data is missing or truncated.")

    if calculate_separations and separations_tmp_path is not None:
        separations_final_path = Path(out_dir) / "neighbors_seps.bin"
        if (Path(separations_tmp_path).exists()):
            os.replace(separations_tmp_path, separations_final_path)
        elif (
            not separations_final_path.is_file()
            or separations_final_path.stat().st_size != total_neighbors * np.dtype(np.float64).itemsize
        ):
            raise ValueError("Completed neighbour-separation data is missing or truncated.")
    else:
        (Path(out_dir) / "neighbors_seps.bin").unlink(missing_ok=True)

    # Save primary neighbor index arrays.
    atomic_save_npy(
        Path(out_dir) / "source_ids.npy",
        final_star_dataframe['internal_id'].values.astype(np.int64)
    )
    atomic_save_npy(
        Path(out_dir) / "offsets.npy",
        offsets
    )

    # Build ID mapping arrays:
    #   - internal_ids          : 1..N
    #   - source_ids (str)  : original external IDs from the CSV
    internal_ids = final_star_dataframe['internal_id'].astype(np.int64).to_numpy()
    source_ids = final_star_dataframe['source_id'].to_numpy()  # dtype=object / str

    # ------------------------------------------------------------------
    # New structure:
    #   - real_ids_int.npy : int64[N], -1 if real source_id is non-numeric
    #   - special_ids.npz  : two arrays for the few non-numeric IDs
    #                        (internal_ids, names)
    # ------------------------------------------------------------------
    real_ids_int = np.full(internal_ids.shape[0], -1, dtype=np.int64)

    special_internal_ids = []
    special_names = []

    # Single pass over all N rows.
    # For most rows, source_ids are pure integers (e.g. Gaia source_id).
    # For those, we store the numeric value in real_ids_int.
    # For the rest (e.g. "HD 216608A"), we store them in special_ids.npz.
    for i, (internal_id, sid) in enumerate(zip(internal_ids, source_ids)):
        # Treat None or non-string as "special".
        if sid is None:
            special_internal_ids.append(int(internal_id))
            special_names.append(str(sid))
            continue

        try:
            # Try to interpret the ID as an integer (fast path: Gaia-like IDs).
            val = int(sid)
            if (0 <= val <= np.iinfo(np.int64).max):
                real_ids_int[i] = val
            else:
                special_internal_ids.append(int(internal_id))
                special_names.append(str(sid))
        except (ValueError, TypeError):
            # Non-numeric IDs end up here (e.g. "HD 216608A").
            special_internal_ids.append(int(internal_id))
            special_names.append(str(sid))

    # Save numeric real IDs (one int64 per row).
    real_ids_int_path = os.path.join(out_dir, "real_ids_int.npy")
    atomic_save_npy(real_ids_int_path, real_ids_int)

    # Save special ID mapping (a tiny NPZ file).
    special_ids_path = os.path.join(out_dir, "special_ids.npz")
    atomic_save_npz(
        special_ids_path,
        internal_ids=np.array(special_internal_ids, dtype=np.int64),
        names=np.asarray(special_names, dtype=np.str_)
    )

    numeric_mask = real_ids_int >= 0
    numeric_indices = np.nonzero(numeric_mask)[0].astype(np.int64)
    numeric_real_ids = real_ids_int[numeric_mask]
    numeric_order = np.argsort(numeric_real_ids, kind="stable")
    atomic_save_npy(
        Path(out_dir) / "numeric_real_ids_sorted.npy",
        numeric_real_ids[numeric_order].astype(np.int64, copy=False),
    )
    atomic_save_npy(
        Path(out_dir) / "numeric_internal_ids_sorted.npy",
        (numeric_indices[numeric_order] + 1).astype(np.int64, copy=False),
    )

    # If desired, the old full NPZ mapping could be kept as well:
    # out_path = os.path.join(out_dir, "id_map_internal_to_real.npz")
    # np.savez_compressed(out_path, internal_ids=internal_ids, source_ids=source_ids.astype(str))

    # Save full catalog for inspection / secondary analyses.
    master_path = os.path.join(out_dir, "master_catalog.parquet")
    master_temporary_path = master_path + ".tmp"
    try:
        final_star_dataframe.to_parquet(master_temporary_path, index=False, compression='snappy')
        os.replace(master_temporary_path, master_path)
    except ImportError:
        master_path = os.path.join(out_dir, "master_catalog.csv")
        master_temporary_path = master_path + ".tmp"
        final_star_dataframe.to_csv(master_temporary_path, index=False)
        os.replace(master_temporary_path, master_path)
        logger.warning(
            "Could not save master_catalog.parquet because no Parquet engine is installed. "
            f"Saved CSV fallback instead: {master_path}"
        )

    # Save numeric columns as standalone arrays for low-memory queries.
    ra_path = os.path.join(out_dir, "ra.npy")
    dec_path = os.path.join(out_dir, "dec.npy")
    gmag_path = os.path.join(out_dir, "phot_g_mean_mag.npy")

    atomic_save_npy(
        ra_path,
        final_star_dataframe['ra'].to_numpy(dtype=np.float64)
    )
    atomic_save_npy(
        dec_path,
        final_star_dataframe['dec'].to_numpy(dtype=np.float64)
    )

    if 'phot_g_mean_mag' in final_star_dataframe.columns:
        atomic_save_npy(
            gmag_path,
            final_star_dataframe['phot_g_mean_mag'].to_numpy(dtype=np.float64)
        )

    magnitude_bands = magnitude_band_manifest(magnitude_columns, phot_g_mean_mag_column)
    for metadata in magnitude_bands.values():
        array_file = metadata["array_file"]
        if (array_file == "phot_g_mean_mag.npy"):
            continue
        column_name = Path(array_file).stem
        if (column_name in final_star_dataframe.columns):
            atomic_save_npy(
                Path(out_dir) / array_file,
                final_star_dataframe[column_name].to_numpy(dtype=np.float64),
            )

    stellar_parameters = stellar_parameter_manifest(stellar_parameter_columns or {})
    for metadata in stellar_parameters.values():
        array_file = metadata["array_file"]
        column_name = Path(array_file).stem
        atomic_save_npy(
            Path(out_dir) / array_file,
            final_star_dataframe[column_name].to_numpy(dtype=np.float64),
        )

    manifest = IndexManifest(
        format_version=2,
        status="complete",
        build_signature=build_signature_value,
        catalog_sha256=catalog_sha256,
        max_radius_arcsec=max_radius_arcsec,
        number_of_sources=len(final_star_dataframe),
        total_neighbors=total_neighbors,
        calculate_separations=calculate_separations,
        magnitude_bands=magnitude_bands,
        stellar_parameters=stellar_parameters,
    )
    write_index_manifest(manifest_path, manifest)
    validate_index_structure(index_paths(out_dir), manifest)

    return master_path


# ============================================================
# MAIN EXECUTION
# ============================================================

def run_build(config_build: BuildConfig) -> int:
    """Build one already-validated configuration while its output lock is held."""
    # --- Load minimal catalog ---
    logger.info("Loading input catalog...")
    final_star_dataframe = load_star_dataframe(
        config_build.input_catalog,
        config_build.use_dask,
        config_build.source_id_column,
        config_build.ra_column,
        config_build.dec_column,
        config_build.phot_g_mean_mag_column,
        config_build.magnitude_columns,
        config_build.stellar_parameter_columns,
    )

    catalog_digest = sha256_file(config_build.input_catalog)
    current_build_signature = build_signature(
        catalog_sha256=catalog_digest,
        max_radius_arcsec=config_build.max_radius_arcsec,
        calculate_separations=config_build.calculate_separations,
        columns=config_build.usecolumns,
        magnitude_columns=config_build.magnitude_columns,
        stellar_parameter_columns=config_build.stellar_parameter_columns,
    )
    existing_manifest_path = Path(config_build.out_dir) / INDEX_MANIFEST_FILENAME
    if (existing_manifest_path.is_file()):
        try:
            existing_manifest = load_index_manifest(existing_manifest_path)
            if (existing_manifest.build_signature == current_build_signature):
                validate_index_structure(index_paths(config_build.out_dir), existing_manifest)
                logger.info("A complete index already matches the current catalog and settings.")
                return 0
            logger.info("Build inputs changed; replacing the existing index.")
        except ValueError as error:
            logger.warning("Existing index is incomplete or invalid and will be rebuilt: %s", error)

    # Compute 3D coordinates and KDTree.
    coords = convert_ra_dec_to_unit_vectors(final_star_dataframe)
    chord_radius = compute_chord_radius(config_build.max_radius_arcsec)
    coordinate_tree = build_or_load_kdtree(coords)

    number_of_stars_in_dataframe = len(final_star_dataframe)
    logger.info(
        f"Querying neighbors within {config_build.max_radius_arcsec:.1f}\" "
        f"for {number_of_stars_in_dataframe} sources..."
    )

    # Temporary files for neighbor IDs and separations.
    neighbors_tmp_path = os.path.join(config_build.out_dir, "neighbors_ids.tmp")
    separations_tmp_path = (
        os.path.join(config_build.out_dir, "neighbors_seps.tmp")
        if config_build.calculate_separations else
        None
    )

    # Load or initialize checkpoint.
    checkpoint_path = os.path.join(config_build.out_dir, "resume_checkpoint.npz")
    checkpoint_index, offsets, checkpoint_total = resume_from_checkpoint(
        checkpoint_path,
        number_of_stars_in_dataframe,
        current_build_signature,
    )

    checkpoint_complete = checkpoint_index == number_of_stars_in_dataframe
    if (checkpoint_index > 0):
        reconcile_resume_file(
            neighbors_tmp_path,
            os.path.join(config_build.out_dir, "neighbors_ids.bin"),
            checkpoint_total * np.dtype(np.int64).itemsize,
            checkpoint_complete=checkpoint_complete,
        )
        if config_build.calculate_separations and separations_tmp_path is not None:
            reconcile_resume_file(
                separations_tmp_path,
                os.path.join(config_build.out_dir, "neighbors_seps.bin"),
                checkpoint_total * np.dtype(np.float64).itemsize,
                checkpoint_complete=checkpoint_complete,
            )

    if (not checkpoint_complete):
        # Open binary files in append mode if resuming, else write mode.
        neighbors_file = open(
            neighbors_tmp_path,
            "ab" if checkpoint_index > 0 else "wb"
        )

        separations_file = None
        if config_build.calculate_separations and separations_tmp_path is not None:
            separations_file = open(
                separations_tmp_path,
                "ab" if checkpoint_index > 0 else "wb"
            )

        # Main computation: fill neighbors_ids.bin + offsets (CSR).
        final_star_dataframe, offsets, checkpoint_total = calculate_contaminants(
            checkpoint_index=checkpoint_index,
            number_of_stars_in_dataframe=number_of_stars_in_dataframe,
            chunk_size=config_build.chunk_size,
            coords=coords,
            chord_radius=chord_radius,
            coordinate_tree=coordinate_tree,
            offsets=offsets,
            checkpoint_total=checkpoint_total,
            final_star_dataframe=final_star_dataframe,
            neighbors_file=neighbors_file,
            separations_file=separations_file,
            buffer_flush_interval=config_build.buffer_flush_interval,
            calculate_separations=config_build.calculate_separations,
            checkpoint_path=checkpoint_path,
            build_signature_value=current_build_signature,
        )

    # Finalize files and write auxiliary arrays.
    with ActivityBar("[saving index outputs]"):
        master_path = save_final_outputs(
            out_dir=config_build.out_dir,
            final_star_dataframe=final_star_dataframe,
            offsets=offsets,
            neighbors_tmp_path=neighbors_tmp_path,
            separations_tmp_path=separations_tmp_path,
            calculate_separations=config_build.calculate_separations,
            build_signature_value=current_build_signature,
            catalog_sha256=catalog_digest,
            max_radius_arcsec=config_build.max_radius_arcsec,
            total_neighbors=checkpoint_total,
            magnitude_columns=config_build.magnitude_columns,
            phot_g_mean_mag_column=config_build.phot_g_mean_mag_column,
            stellar_parameter_columns=config_build.stellar_parameter_columns,
        )
    Path(checkpoint_path).unlink(missing_ok=True)

    # Summary.
    logger.info("")
    logger.info(f"Index saved to: {config_build.out_dir}")
    logger.info(f" - source_ids.npy: {number_of_stars_in_dataframe}")
    logger.info(f" - offsets.npy: {offsets.shape}")
    logger.info(f" - neighbors_ids.bin: written ({checkpoint_total} total neighbors)")
    if config_build.calculate_separations:
        logger.info(" - neighbors_seps.bin: written")
    logger.info(f" - master_catalog.parquet: {master_path}")
    logger.info(" - KDTree: built safely in memory")
    logger.info("Build step finished.")

    return 0


def main(config_path: str | Path | None = None) -> int:
    """Build an index only after configuration parsing and runtime validation succeed."""
    config_build = load_config("build_neighbors_index", config_path)
    if (not isinstance(config_build, BuildConfig)):
        raise RuntimeError("Failed to load build configuration.")

    # Runtime directory creation happens after pure parsing and filesystem validation.
    ensure_directory(config_build.out_dir, "build_neighbors_index.io.out_dir")
    with exclusive_build_lock(config_build.out_dir):
        return run_build(config_build)


if (__name__ == "__main__"):
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.error("Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        logger.error("ERROR:\n%s", exc)
        raise SystemExit(1)
