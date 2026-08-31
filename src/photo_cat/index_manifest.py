# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Versioned metadata and structural validation for PHOTO-CAT indexes."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

import numpy as np


INDEX_FORMAT_VERSION: Final[int] = 2
INDEX_MANIFEST_FILENAME: Final[str] = "index_manifest.json"


@dataclass(frozen=True)
class IndexManifest:
    """Metadata needed to prove that an index is complete and query-compatible."""

    format_version: int
    status: str
    build_signature: str
    catalog_sha256: str
    max_radius_arcsec: float
    number_of_sources: int
    total_neighbors: int
    calculate_separations: bool
    magnitude_bands: dict[str, dict[str, str]] | None = None
    stellar_parameters: dict[str, dict[str, str]] | None = None


def sha256_file(path: str | Path, block_size: int = 1024 * 1024) -> str:
    """Return a streaming SHA-256 digest without loading a catalogue into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        while block := file.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def build_signature(
    *,
    catalog_sha256: str,
    max_radius_arcsec: float,
    calculate_separations: bool,
    columns: list[str],
    magnitude_columns: dict[str, str] | None = None,
    stellar_parameter_columns: dict[str, str] | None = None,
) -> str:
    """Hash every input that changes neighbour-index semantics."""
    payload = {
        "catalog_sha256": catalog_sha256,
        "max_radius_arcsec": max_radius_arcsec,
        "calculate_separations": calculate_separations,
        "columns": columns,
        "magnitude_columns": magnitude_columns or {},
        "stellar_parameter_columns": stellar_parameter_columns or {},
        "format_version": INDEX_FORMAT_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_json(path: str | Path, payload: dict[str, Any]) -> None:
    """Write JSON beside its destination and publish it with one replace."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_save_npy(path: str | Path, array: np.ndarray) -> None:
    """Publish one NumPy array without exposing a partially written file."""
    destination = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            np.save(file, array, allow_pickle=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def atomic_save_npz(path: str | Path, **arrays: np.ndarray) -> None:
    """Publish one compressed NumPy archive containing only safe arrays."""
    destination = Path(path)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.",
        suffix=".tmp",
        dir=destination.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            np.savez_compressed(file, **arrays)  # type: ignore[arg-type]  # numpy stub misreads **kwargs
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_index_manifest(path: str | Path, manifest: IndexManifest) -> None:
    """Publish a completed index manifest atomically."""
    atomic_write_json(path, asdict(manifest))


def load_index_manifest(path: str | Path) -> IndexManifest:
    """Load and validate the small, non-executable index metadata document."""
    manifest_path = Path(path)
    if (not manifest_path.is_file()):
        raise ValueError(
            "This index uses the legacy unsafe format or is incomplete.\n\n"
            f"Missing {INDEX_MANIFEST_FILENAME}: {manifest_path}\n\n"
            "Rebuild the index with the current PHOTO-CAT version before querying it."
        )

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = IndexManifest(
            format_version=int(data["format_version"]),
            status=str(data["status"]),
            build_signature=str(data["build_signature"]),
            catalog_sha256=str(data["catalog_sha256"]),
            max_radius_arcsec=float(data["max_radius_arcsec"]),
            number_of_sources=int(data["number_of_sources"]),
            total_neighbors=int(data["total_neighbors"]),
            calculate_separations=bool(data["calculate_separations"]),
            magnitude_bands=data.get("magnitude_bands"),
            stellar_parameters=data.get("stellar_parameters"),
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Index manifest is malformed: {manifest_path}") from error

    if (manifest.format_version != INDEX_FORMAT_VERSION):
        raise ValueError(
            f"Unsupported index format version {manifest.format_version}; "
            f"this PHOTO-CAT version requires {INDEX_FORMAT_VERSION}. Rebuild the index."
        )
    if (manifest.status != "complete"):
        raise ValueError("The selected index is not marked complete. Resume or rebuild it first.")
    if (manifest.number_of_sources <= 0 or manifest.total_neighbors < 0):
        raise ValueError("Index manifest contains invalid source or neighbour counts.")
    if (not np.isfinite(manifest.max_radius_arcsec) or manifest.max_radius_arcsec <= 0.0):
        raise ValueError("Index manifest contains an invalid build radius.")
    return manifest


def _load_vector(path: Path, dtype: np.dtype, expected_length: int, label: str) -> np.ndarray:
    """Open one safe NumPy vector and enforce its public index contract."""
    try:
        array = np.load(path, mmap_mode="r", allow_pickle=False)
    except (OSError, ValueError) as error:
        raise ValueError(f"Could not safely load {label}: {path}") from error

    if (array.ndim != 1 or array.shape[0] != expected_length or array.dtype != dtype):
        raise ValueError(
            f"Invalid {label}: expected {dtype.name}[{expected_length}], "
            f"found dtype={array.dtype}, shape={array.shape}."
        )
    return array


def validate_index_structure(paths: Any, manifest: IndexManifest) -> None:
    """Reject truncated, mismatched, or executable index payloads before querying."""
    count = manifest.number_of_sources
    offsets = _load_vector(paths.offsets, np.dtype(np.int64), count + 1, "offsets.npy")
    _load_vector(paths.ra, np.dtype(np.float64), count, "ra.npy")
    _load_vector(paths.dec, np.dtype(np.float64), count, "dec.npy")
    _load_vector(paths.phot_g_mean_mag, np.dtype(np.float64), count, "phot_g_mean_mag.npy")
    for band, metadata in (manifest.magnitude_bands or {}).items():
        array_file = metadata.get("array_file") if isinstance(metadata, dict) else None
        if (not isinstance(array_file, str) or array_file.strip() == ""):
            raise ValueError(f"Index manifest magnitude band {band!r} is malformed.")
        if (array_file != "phot_g_mean_mag.npy"):
            _load_vector(paths.root / array_file, np.dtype(np.float64), count, f"{array_file}")
    for parameter, metadata in (manifest.stellar_parameters or {}).items():
        array_file = metadata.get("array_file") if isinstance(metadata, dict) else None
        if (not isinstance(array_file, str) or array_file.strip() == ""):
            raise ValueError(f"Index manifest stellar parameter {parameter!r} is malformed.")
        _load_vector(paths.root / array_file, np.dtype(np.float64), count, f"{array_file}")
    _load_vector(paths.real_ids_int, np.dtype(np.int64), count, "real_ids_int.npy")

    if (int(offsets[0]) != 0 or np.any(offsets[1:] < offsets[:-1])):
        raise ValueError("Invalid offsets.npy: offsets must start at zero and be monotonically increasing.")
    if (int(offsets[-1]) != manifest.total_neighbors):
        raise ValueError("Index neighbour count does not match offsets.npy.")

    expected_neighbor_bytes = manifest.total_neighbors * np.dtype(np.int64).itemsize
    if (paths.neighbors_ids.stat().st_size != expected_neighbor_bytes):
        raise ValueError(
            "neighbors_ids.bin size does not match the completed index manifest. Rebuild the index."
        )
    if (manifest.calculate_separations):
        expected_separation_bytes = manifest.total_neighbors * np.dtype(np.float64).itemsize
        if (
            not paths.neighbors_seps.is_file()
            or paths.neighbors_seps.stat().st_size != expected_separation_bytes
        ):
            raise ValueError(
                "neighbors_seps.bin is missing or does not match the completed index manifest."
            )

    numeric_real = np.load(paths.numeric_real_ids_sorted, mmap_mode="r", allow_pickle=False)
    numeric_internal = np.load(paths.numeric_internal_ids_sorted, mmap_mode="r", allow_pickle=False)
    if (
        numeric_real.ndim != 1
        or numeric_internal.ndim != 1
        or numeric_real.dtype != np.int64
        or numeric_internal.dtype != np.int64
        or numeric_real.shape != numeric_internal.shape
        or np.any(numeric_real[1:] < numeric_real[:-1])
        or np.any((numeric_internal < 1) | (numeric_internal > count))
    ):
        raise ValueError("Persisted numeric source-ID lookup arrays are invalid.")

    try:
        with np.load(paths.special_ids, allow_pickle=False) as special:
            special_internal = special["internal_ids"]
            special_names = special["names"]
    except (KeyError, OSError, ValueError) as error:
        raise ValueError(
            "special_ids.npz is unsafe or malformed. Rebuild this legacy index before querying it."
        ) from error

    if (
        special_internal.ndim != 1
        or special_names.ndim != 1
        or special_internal.dtype != np.int64
        or special_names.dtype.kind not in {"U", "S"}
        or special_internal.shape != special_names.shape
        or np.any((special_internal < 1) | (special_internal > count))
    ):
        raise ValueError("special_ids.npz does not match the completed index manifest.")
