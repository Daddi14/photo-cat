#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""PHOTO-CAT environment self-check."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
from pathlib import Path


PACKAGE_NAME = "photo-cat"

REQUIRED_IMPORTS = [
    ("numpy", "NumPy"),
    ("pandas", "pandas"),
    ("scipy", "SciPy"),
    ("tqdm", "tqdm"),
    ("yaml", "PyYAML"),
    ("pyarrow", "PyArrow"),
    ("dask", "Dask"),
]


def status_line(ok: bool, label: str, detail: str = "") -> None:
    prefix = "[ OK ]" if ok else "[FAIL]"
    if (detail):
        print(f"{prefix} {label}: {detail}")
    else:
        print(f"{prefix} {label}")


def info_line(label: str, detail: str = "") -> None:
    if (detail):
        print(f"[INFO] {label}: {detail}")
    else:
        print(f"[INFO] {label}")


def candidate_project_dirs() -> list[Path]:
    candidates = [Path.cwd().resolve()]

    try:
        source_candidate = Path(__file__).resolve().parents[2]
        candidates.append(source_candidate)
    except IndexError:
        pass

    unique_candidates: list[Path] = []
    for candidate in candidates:
        if (candidate not in unique_candidates):
            unique_candidates.append(candidate)

    return unique_candidates


def find_project_dir() -> Path | None:
    """Find a PHOTO-CAT source/release folder when doctor is run from one."""
    for candidate in candidate_project_dirs():
        source_layout = ((candidate / "pyproject.toml").is_file() and (candidate / "src" / "photo_cat").is_dir())
        release_layout = ((candidate / "VERSION").is_file() and (candidate / "config.yaml").is_file() and (candidate / "scripts").is_dir())

        if (source_layout or release_layout):
            return candidate.resolve()

    return None


def read_project_version(project_dir: Path | None) -> str | None:
    if (project_dir is None):
        return None

    version_file = project_dir / "VERSION"
    try:
        version = version_file.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None

    return version or None


def installed_package_version() -> str | None:
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return None


def resolve_config_path(
    project_dir: Path | None,
    explicit_config_path: str | Path | None = None,
) -> tuple[Path | None, bool]:
    """Resolve explicit, environment, and project-local config paths in that order."""
    if (explicit_config_path is not None):
        return Path(os.path.expanduser(str(explicit_config_path))).resolve(), True

    config_from_env = os.environ.get("PHOTO_CAT_CONFIG")
    if (config_from_env):
        return Path(os.path.expanduser(config_from_env)).resolve(), True

    if (project_dir is not None):
        return (project_dir / "config.yaml").resolve(), False

    return None, False


def check_python_version() -> bool:
    version = sys.version_info
    ok = ((version.major, version.minor) >= (3, 10) and (version.major, version.minor) < (3, 14))
    status_line(ok, "Python", sys.version.split()[0])
    return ok


def check_tkinter() -> bool:
    try:
        import tkinter  # noqa: F401

        status_line(True, "Tkinter")
        return True
    except Exception as exc:
        status_line(False, "Tkinter", str(exc))
        return False


def check_package_version(project_dir: Path | None) -> bool:
    installed = installed_package_version()
    expected = read_project_version(project_dir)

    if (installed is None):
        status_line(False, "PHOTO-CAT package", "not installed in this environment")
        return False

    if (expected is None):
        status_line(True, "PHOTO-CAT package", f"installed {installed}")
        return True

    ok = (installed == expected)
    status_line(ok, "PHOTO-CAT package", f"installed {installed}, expected {expected}")
    return ok


def check_imports() -> bool:
    all_ok = True

    for module_name, display_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
            status_line(True, display_name)
        except Exception as exc:
            all_ok = False
            status_line(False, display_name, str(exc))

    return all_ok


def check_project_context(project_dir: Path | None, explicit_config_path: str | Path | None = None) -> bool:
    """Check project resources with an explicit config selection when supplied."""
    config_path, explicit_config = resolve_config_path(project_dir, explicit_config_path)

    if (project_dir is None):
        info_line("Project folder", "not checked in package-install mode")

        if (config_path is None):
            info_line("config.yaml", "not checked; pass --config when validating a run configuration")
            info_line(".venv", "not checked in package-install mode")
            info_line(".runtime", "not checked in package-install mode")
            return True

        ok = config_path.is_file()
        status_line(ok, "config.yaml", str(config_path))
        info_line(".venv", "not checked in package-install mode")
        info_line(".runtime", "not checked in package-install mode")
        return ok

    status_line(True, "Project folder", str(project_dir))

    version_file = project_dir / "VERSION"
    version_ok = version_file.is_file()
    status_line(version_ok, "VERSION", str(version_file))

    all_ok = version_ok

    if (config_path is not None):
        config_ok = config_path.is_file()
        label = "config.yaml" if (not explicit_config) else "config"
        status_line(config_ok, label, str(config_path))
        all_ok = all_ok and config_ok

    venv_dir = project_dir / ".venv"
    if (venv_dir.exists()):
        status_line(venv_dir.is_dir(), ".venv", str(venv_dir))
        all_ok = all_ok and venv_dir.is_dir()
    else:
        info_line(".venv", "not present; run a launcher to create the local environment")

    runtime_dir = project_dir / ".runtime"
    runtime_detail = str(runtime_dir) if runtime_dir.exists() else "not present; only needed when no suitable system Python exists"
    info_line(".runtime", runtime_detail)

    return all_ok


def main(config_path: str | Path | None = None) -> int:
    """Run diagnostics without requiring callers to mutate PHOTO_CAT_CONFIG."""
    project_dir = find_project_dir()

    print("PHOTO-CAT environment check")
    print("=" * 72)

    checks = [
        check_python_version(),
        check_tkinter(),
        check_package_version(project_dir),
        check_imports(),
        check_project_context(project_dir, config_path),
    ]

    print("=" * 72)

    if (all(checks)):
        print("PHOTO-CAT environment looks ready.")
        return 0

    print("PHOTO-CAT environment check found issues.")
    print("Review the failed checks above. If running from a release folder, run START_WINDOWS.bat or START_UNIX.sh again to repair the local environment.")
    return 1


if (__name__ == "__main__"):
    raise SystemExit(main())
