# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Central path-resolution and filesystem policy for PHOTO-CAT runtime code."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final


INDEX_REQUIRED_FILENAMES: Final[tuple[str, ...]] = (
    "offsets.npy",
    "neighbors_ids.bin",
    "ra.npy",
    "dec.npy",
    "phot_g_mean_mag.npy",
    "real_ids_int.npy",
    "special_ids.npz",
)


@dataclass(frozen=True)
class IndexPaths:
    """Resolved paths for one completed PHOTO-CAT neighbour index."""

    root: Path
    offsets: Path
    neighbors_ids: Path
    ra: Path
    dec: Path
    phot_g_mean_mag: Path
    real_ids_int: Path
    special_ids: Path
    output_dir: Path


def resolve_user_path(path_value: str | Path | None, base_dir: Path) -> Path | None:
    """Resolve a user-supplied path relative to an explicit base directory.

    Empty values resolve to ``None``. The caller owns policy such as whether a
    missing value is allowed or whether the resulting path must already exist.
    """
    if (path_value is None):
        return None

    path_text = str(path_value).strip()
    if (path_text == ""):
        return None

    path = Path(os.path.expanduser(path_text))
    if (not path.is_absolute()):
        path = base_dir / path

    return path.resolve()


def resolve_config_file_path(
    config_path: str | Path | None,
    *,
    base_dir: Path,
    default_path: Path,
    environment_path: str | None = None,
) -> Path:
    """Resolve explicit, environment, and default configuration locations in order."""
    selected_path: str | Path
    if (config_path is not None):
        selected_path = config_path
    elif (environment_path is not None and environment_path.strip() != ""):
        selected_path = environment_path
    else:
        selected_path = default_path

    resolved_path = resolve_user_path(selected_path, base_dir)
    if (resolved_path is None):
        raise ValueError("Configuration path cannot be empty.")

    return resolved_path


def require_existing_file(path: Path | None, label: str) -> Path | None:
    """Return an existing file path or raise a direct user-facing error."""
    if (path is None):
        return None

    if (not path.is_file()):
        raise FileNotFoundError(
            f"{label} was not found: {path}\n"
            "Check config.yaml and use / in paths, even on Windows."
        )

    return path


def validate_directory_target(path: Path, label: str) -> Path:
    """Reject a configured directory path that is already occupied by a file."""
    if (path.exists() and not path.is_dir()):
        raise ValueError(
            f"{label} must be a directory, but it points to an existing file:\n{path}\n\n"
            "Choose a new output folder or remove/rename the conflicting file."
        )

    return path


def ensure_directory(path: str | Path, label: str) -> Path:
    """Create a validated runtime directory after configuration parsing has completed."""
    directory = validate_directory_target(Path(path), label)

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise OSError(f"Could not create {label}: {directory}") from error

    return directory


def validate_filename_only(value: str, label: str) -> str:
    """Require a child filename instead of a path that could escape its folder."""
    filename = str(value).strip()
    if (filename == ""):
        raise ValueError(f"{label} cannot be empty.")

    if (filename in {".", ".."} or "/" in filename or "\\" in filename):
        raise ValueError(
            f"{label} must be a filename only, not a path: {filename}\n"
            "Use --out-dir/config out_dir to choose the folder."
        )

    return filename


def index_paths(index_dir: str | Path) -> IndexPaths:
    """Return named index paths without performing filesystem validation."""
    root = Path(index_dir).expanduser().resolve()
    return IndexPaths(
        root=root,
        offsets=root / "offsets.npy",
        neighbors_ids=root / "neighbors_ids.bin",
        ra=root / "ra.npy",
        dec=root / "dec.npy",
        phot_g_mean_mag=root / "phot_g_mean_mag.npy",
        real_ids_int=root / "real_ids_int.npy",
        special_ids=root / "special_ids.npz",
        output_dir=root / "output",
    )


def validate_index_paths(paths: IndexPaths) -> IndexPaths:
    """Validate an index directory and all files required by query execution."""
    if (not paths.root.exists()):
        raise FileNotFoundError(
            "Query index folder was not found.\n\n"
            f"Selected index folder:\n{paths.root}\n\n"
            "Run the build step first, or select the correct Output/index folder."
        )

    if (not paths.root.is_dir()):
        raise ValueError(
            "Query index folder must be a directory, but it points to a file.\n\n"
            f"Selected path:\n{paths.root}"
        )

    missing_files = [name for name in INDEX_REQUIRED_FILENAMES if (not (paths.root / name).is_file())]
    if (missing_files):
        raise FileNotFoundError(
            "Query index folder is not ready.\n\n"
            f"Selected index folder:\n{paths.root}\n\n"
            "Missing required index files:\n"
            + "\n".join(f"- {name}" for name in missing_files)
            + "\n\nRun the build step first, or select the correct Output/index folder."
        )

    return paths


def ensure_query_output_directory(paths: IndexPaths) -> Path:
    """Create the query-result directory while rejecting file path conflicts."""
    if (paths.output_dir.exists() and not paths.output_dir.is_dir()):
        raise ValueError(
            "Query results output path must be a directory, but it points to a file.\n\n"
            f"Conflicting path:\n{paths.output_dir}\n\n"
            "Remove/rename the file or select a different index folder."
        )

    return ensure_directory(paths.output_dir, "query results output folder")


def query_output_json_path(
    paths: IndexPaths,
    targets_input: str | None,
    field_of_view_arcsec: float,
    delta_mag: float,
    *,
    now: datetime | None = None,
) -> Path:
    """Build a timestamped query-result path within the controlled output directory."""
    output_dir = ensure_query_output_directory(paths)
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M")
    target_name = Path(targets_input).stem if (targets_input is not None) else "manual_targets"
    filename = f"{target_name}_FoV{int(field_of_view_arcsec)}_dmag{int(delta_mag)}_{timestamp}.json"
    return output_dir / filename
