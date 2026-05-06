#!/usr/bin/env python3
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
            * names    : object[:] -> the original string IDs for those rows
        Only a tiny subset of the catalog (e.g. ~2000 rows) will be stored here.

    - ckdtree.pkl
        Pickled scipy.spatial.cKDTree built on 3D unit vectors (RA/Dec on sphere)
        for fast neighbor queries. Reused to resume computations.

Key ideas
---------
    - Convert RA/Dec to 3D unit vectors and use cKDTree with chord distance
      for angular neighbor searches on the sphere.
    - Process sources in chunks to keep memory usage under control.
    - Stream neighbors to disk with small Python buffers and periodic flushes.
    - Save a checkpoint with CSR offsets and total neighbor count to resume
      after interruptions without restarting from scratch.

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
import os
import pickle
import sys
from typing import List

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from tqdm import tqdm
from numpy.typing import NDArray

from logger_setup import get_logger
from load_config import load_config
from pipeline_display import ActivityBar, progress_bar, tqdm_options


logger = get_logger(__name__)


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
    phot_g_mean_mag_column: str = "phot_g_mean_mag"
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

    usecolumns = [
        source_id_column,
        ra_column,
        dec_column,
        phot_g_mean_mag_column,
    ]

    if (any(column == "" for column in usecolumns)):
        raise ValueError("Catalog column names cannot be empty.")

    if (len(set(usecolumns)) != len(usecolumns)):
        raise ValueError("Catalog Source ID, RA, Dec, and magnitude columns must be different.")

    logger.info("Catalog column mapping:")
    logger.info(f" - source_id: {source_id_column}")
    logger.info(f" - ra: {ra_column}")
    logger.info(f" - dec: {dec_column}")
    logger.info(f" - phot_g_mean_mag: {phot_g_mean_mag_column}")

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

    logger.info(f"Loaded {len(star_dataframe)} rows.")

    if (len(star_dataframe) == 0):
        raise ValueError(
            "The catalog CSV was read successfully, but it contains no data rows.\n"
            "Add at least one catalog row below the header."
        )

    numeric_columns = ["ra", "dec", "phot_g_mean_mag"]
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

    # Drop rows missing mandatory fields and normalize IDs to strings.
    rows_before_drop = len(star_dataframe)
    final_star_dataframe = star_dataframe.dropna(
        subset=['source_id', 'ra', 'dec', 'phot_g_mean_mag']
    ).reset_index(drop=True)
    rows_after_drop = len(final_star_dataframe)
    dropped_rows = rows_before_drop - rows_after_drop

    if (dropped_rows > 0):
        logger.warning(
            "Dropped %s catalog rows because source_id, RA, Dec, or magnitude was empty/non-numeric.",
            dropped_rows
        )

    if (rows_after_drop == 0):
        raise ValueError(
            "No valid catalog rows remain after cleaning.\n\n"
            "Every usable row must have source_id, RA, Dec, and magnitude values."
        )

    final_star_dataframe['source_id'] = final_star_dataframe['source_id'].astype(str)

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
    out_dir: str,
    kdtree_filename: str = "ckdtree.pkl"
) -> tuple[cKDTree, str]:
    """
    Build a cKDTree on the 3D unit vectors, or load a previously built tree
    from disk if it exists.

    Parameters
    ----------
    coords : numpy.ndarray
        Unit vectors with shape (N, 3).

    out_dir : str
        Directory where the KDTree pickle is stored or should be created.

    kdtree_filename : str, optional
        File name for the KDTree pickle (default: "ckdtree.pkl").

    Returns
    -------
    coordinate_tree : scipy.spatial.cKDTree
        KDTree instance ready for query_ball_point searches.

    tree_path : str
        Full path to the KDTree pickle file.
    """
    tree_path = os.path.join(out_dir, kdtree_filename)

    if os.path.exists(tree_path):
        logger.info(f"Loading existing KDTree from {tree_path} ...")
        with ActivityBar("[loading KDTree]"):
            with open(tree_path, "rb") as f:
                coordinate_tree = pickle.load(f)
    else:
        logger.info("Building cKDTree...")
        with ActivityBar("[building KDTree]"):
            coordinate_tree = cKDTree(coords)
            with open(tree_path, "wb") as f:
                pickle.dump(coordinate_tree, f)
        logger.info(f"Saved KDTree to {tree_path}")

    return coordinate_tree, tree_path


def resume_from_checkpoint(
    checkpoint_path: str,
    number_of_stars_in_dataframe: int
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
        checkpoint = np.load(checkpoint_path)
        checkpoint_index = int(checkpoint["start_index"])

        if checkpoint_index >= number_of_stars_in_dataframe:
            logger.info(
                "Checkpoint indicates index already completed. Exiting without changes."
            )
            sys.exit(0)

        offsets = checkpoint["offsets"]
        checkpoint_total = int(checkpoint["total"])
        logger.info(f"[RESUME] Found checkpoint. Resuming from index {checkpoint_index}.")
    else:
        # Fresh run: allocate offsets (N+1) and start at 0 neighbors.
        offsets = np.empty(number_of_stars_in_dataframe + 1, dtype=np.int64)
        offsets[0] = 0
        checkpoint_total = 0
        logger.info("No checkpoint found. Starting from the beginning.\n")

    return checkpoint_index, offsets, checkpoint_total


def calculate_contaminants(
    checkpoint_index: int,
    number_of_stars_in_dataframe: int,
    chunk_size: int,
    coords: np.ndarray,
    chord_radius: np.float64,
    coordinate_tree: cKDTree,
    offsets: np.ndarray,
    checkpoint_total: int,
    final_star_dataframe: pd.DataFrame,
    neighbors_file,
    separations_file,
    buffer_flush_interval: int,
    calculate_separations: bool,
    checkpoint_path: str
):
    """
    Main streaming loop: query neighbors for each star, write a CSR index
    to disk, and periodically checkpoint progress.

    Parameters
    ----------
    checkpoint_index : int
        Starting index for this run (0 for fresh run, >0 when resuming).

    number_of_stars_in_dataframe : int
        Total number of stars N.

    chunk_size : int
        Number of stars per block to process per KDTree query_ball_point call.

    coords : numpy.ndarray
        (N, 3) unit vectors for each star.

    chord_radius : float
        cKDTree search radius in chord distance units.

    coordinate_tree : cKDTree
        KDTree built on coords.

    offsets : numpy.ndarray
        CSR offsets array, updated in-place.

    checkpoint_total : int
        Running total of neighbor entries written so far.

    final_star_dataframe : pandas.DataFrame
        Catalog with 'internal_id' column used to map row indices to internal IDs.

    neighbors_file : file-like
        Open binary file handle for neighbors_ids.tmp (to be renamed).

    separations_file : file-like or None
        Open binary file handle for neighbors_seps.tmp, or None if separations
        are not being computed.

    buffer_flush_interval : int
        Number of processed blocks between flushes/checkpoints.

    calculate_separations : bool
        If True, also compute and buffer separations in arcsec.

    checkpoint_path : str
        Where to save np.savez checkpoints.
    """
    logger.info("Building neighbor index (resumable mode)...")

    progress = tqdm(
        total=number_of_stars_in_dataframe,
        initial=checkpoint_index,
        unit="stars",
        **tqdm_options("Building index")
    )

    # Python-side buffers to collect neighbors from several blocks before
    # writing to disk. This amortizes tofile() calls.
    neighbors_buffer = []
    separations_buffer = []
    buffer_index = 0

    for start in range(checkpoint_index, number_of_stars_in_dataframe, chunk_size):
        end = min(number_of_stars_in_dataframe, start + chunk_size)
        block_coords = coords[start:end]

        # query_ball_point returns, for each point in block_coords, a Python list
        # of neighbor indices in the *global* coords array.
        neighbors_indices_lists = coordinate_tree.query_ball_point(
            block_coords,
            r=chord_radius,
            workers=-1
        )

        for i_neighbor, neighbor_indices_list in enumerate(neighbors_indices_lists):
            target_star_index = start + i_neighbor

            # If no neighbors, just propagate the previous total into offsets[i+1].
            if not neighbor_indices_list:
                offsets[target_star_index + 1] = checkpoint_total
                continue

            # Remove self index from neighbor list if present.
            # (The KDTree may return the point itself as a neighbor.)
            if target_star_index in neighbor_indices_list:
                neighbor_indices_list.remove(target_star_index)

            neighbor_indices_array = np.array(neighbor_indices_list, dtype=np.int64)

            # After removing self, there may be no neighbors left.
            if neighbor_indices_array.size == 0:
                offsets[target_star_index + 1] = checkpoint_total
                continue

            # Map neighbor row indices back to internal_ids (1..N).
            contaminant_ids = final_star_dataframe['internal_id'].values[
                neighbor_indices_array
            ].astype(np.int64)
            neighbors_buffer.append(contaminant_ids)

            if calculate_separations:
                # Compute angular separations using dot products between unit vectors:
                #   cos(theta) = u · v
                # Then:
                #   theta = arccos(clipped dot product)
                # And convert to arcsec.
                target_star_unit_vector = coords[target_star_index]
                neighbor_unit_vectors = coords[neighbor_indices_array]

                dot_product = np.dot(neighbor_unit_vectors, target_star_unit_vector)
                dot_product = np.clip(dot_product, -1.0, 1.0)

                angular_separations_rad = np.arccos(dot_product)
                angular_separations_arcsecs = (
                    np.rad2deg(angular_separations_rad) * 3600.0
                ).astype(np.float64)

                separations_buffer.append(angular_separations_arcsecs)

            checkpoint_total += contaminant_ids.size
            # CSR-style: offsets[i+1] is total neighbors up to and including star i.
            offsets[target_star_index + 1] = checkpoint_total

        buffer_index += 1
        progress.update(end - start)

        # Periodically flush buffered neighbors and separations, and write a
        # checkpoint so an interrupted run can resume from 'end'.
        if buffer_index >= buffer_flush_interval:
            if neighbors_buffer:
                np.concatenate(neighbors_buffer).tofile(neighbors_file)
                neighbors_buffer.clear()

            if calculate_separations and separations_buffer:
                np.concatenate(separations_buffer).tofile(separations_file)
                separations_buffer.clear()

            buffer_index = 0

            np.savez(
                checkpoint_path,
                start_index=end,
                offsets=offsets,
                total=checkpoint_total
            )

    # Final flush after the last block.
    if neighbors_buffer:
        np.concatenate(neighbors_buffer).tofile(neighbors_file)

    if calculate_separations and separations_buffer:
        np.concatenate(separations_buffer).tofile(separations_file)

    neighbors_file.close()
    if calculate_separations and separations_file is not None:
        separations_file.close()

    # Final checkpoint: start_index == N means "complete".
    np.savez(
        checkpoint_path,
        start_index=number_of_stars_in_dataframe,
        offsets=offsets,
        total=checkpoint_total
    )

    progress.close()

    return final_star_dataframe, offsets, checkpoint_total


def save_final_outputs(
    out_dir: str,
    final_star_dataframe: pd.DataFrame,
    offsets: np.ndarray,
    neighbors_tmp_path: str,
    separations_tmp_path: str,
    calculate_separations: bool
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
    # Rename temporary neighbor files to their final names.
    os.replace(neighbors_tmp_path, os.path.join(out_dir, "neighbors_ids.bin"))
    if calculate_separations and separations_tmp_path is not None:
        os.replace(separations_tmp_path, os.path.join(out_dir, "neighbors_seps.bin"))

    # Save primary neighbor index arrays.
    np.save(
        os.path.join(out_dir, "source_ids.npy"),
        final_star_dataframe['internal_id'].values.astype(np.int64)
    )
    np.save(
        os.path.join(out_dir, "offsets.npy"),
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
            real_ids_int[i] = val
        except (ValueError, TypeError):
            # Non-numeric IDs end up here (e.g. "HD 216608A").
            special_internal_ids.append(int(internal_id))
            special_names.append(str(sid))

    # Save numeric real IDs (one int64 per row).
    real_ids_int_path = os.path.join(out_dir, "real_ids_int.npy")
    np.save(real_ids_int_path, real_ids_int)

    # Save special ID mapping (a tiny NPZ file).
    special_ids_path = os.path.join(out_dir, "special_ids.npz")
    np.savez_compressed(
        special_ids_path,
        internal_ids=np.array(special_internal_ids, dtype=np.int64),
        names=np.array(special_names, dtype=object)
    )

    # If desired, the old full NPZ mapping could be kept as well:
    # out_path = os.path.join(out_dir, "id_map_internal_to_real.npz")
    # np.savez_compressed(out_path, internal_ids=internal_ids, source_ids=source_ids.astype(str))

    # Save full catalog for inspection / secondary analyses.
    master_path = os.path.join(out_dir, "master_catalog.parquet")
    try:
        final_star_dataframe.to_parquet(master_path, index=False, compression='snappy')
    except ImportError:
        master_path = os.path.join(out_dir, "master_catalog.csv")
        final_star_dataframe.to_csv(master_path, index=False)
        logger.warning(
            "Could not save master_catalog.parquet because no Parquet engine is installed. "
            f"Saved CSV fallback instead: {master_path}"
        )

    # Save numeric columns as standalone arrays for low-memory queries.
    ra_path = os.path.join(out_dir, "ra.npy")
    dec_path = os.path.join(out_dir, "dec.npy")
    gmag_path = os.path.join(out_dir, "phot_g_mean_mag.npy")

    np.save(
        ra_path,
        final_star_dataframe['ra'].to_numpy(dtype=np.float64)
    )
    np.save(
        dec_path,
        final_star_dataframe['dec'].to_numpy(dtype=np.float64)
    )

    if 'phot_g_mean_mag' in final_star_dataframe.columns:
        np.save(
            gmag_path,
            final_star_dataframe['phot_g_mean_mag'].to_numpy(dtype=np.float64)
        )

    return master_path


# ============================================================
# MAIN EXECUTION
# ============================================================

def main() -> int:
    config_build = load_config("build_neighbors_index")

    # Ensure output directory exists.
    os.makedirs(config_build.out_dir, exist_ok=True)

    # --- Load minimal catalog ---
    logger.info("Loading input catalog...")
    final_star_dataframe = load_star_dataframe(
        config_build.input_catalog,
        config_build.use_dask,
        config_build.source_id_column,
        config_build.ra_column,
        config_build.dec_column,
        config_build.phot_g_mean_mag_column
    )

    # Compute 3D coordinates and KDTree.
    coords = convert_ra_dec_to_unit_vectors(final_star_dataframe)
    chord_radius = compute_chord_radius(config_build.max_radius_arcsec)
    coordinate_tree, tree_path = build_or_load_kdtree(
        coords,
        config_build.out_dir,
        config_build.KDTREE_FILENAME
    )

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
        number_of_stars_in_dataframe
    )

    # Open binary files in append mode if resuming, else write mode.
    neighbors_file = open(
        neighbors_tmp_path,
        "ab" if checkpoint_index > 0 else "wb"
    )

    separations_file = None
    if config_build.calculate_separations:
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
        checkpoint_path=checkpoint_path
    )

    # Finalize files and write auxiliary arrays.
    with ActivityBar("[saving index outputs]"):
        master_path = save_final_outputs(
            out_dir=config_build.out_dir,
            final_star_dataframe=final_star_dataframe,
            offsets=offsets,
            neighbors_tmp_path=neighbors_tmp_path,
            separations_tmp_path=separations_tmp_path,
            calculate_separations=config_build.calculate_separations
        )

    # Summary.
    logger.info("")
    logger.info(f"Index saved to: {config_build.out_dir}")
    logger.info(f" - source_ids.npy: {number_of_stars_in_dataframe}")
    logger.info(f" - offsets.npy: {offsets.shape}")
    logger.info(f" - neighbors_ids.bin: written ({checkpoint_total} total neighbors)")
    if config_build.calculate_separations:
        logger.info(" - neighbors_seps.bin: written")
    logger.info(f" - master_catalog.parquet: {master_path}")
    logger.info(f" - KDTree: {tree_path}")
    logger.info("Build step finished.")

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
