#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""PHOTO-CAT environment self-check."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
VERSION_FILE = PROJECT_DIR / "VERSION"
CONFIG_PATH = Path(os.environ.get("PHOTO_CAT_CONFIG", str(PROJECT_DIR / "config.yaml"))).resolve()
VENV_DIR = PROJECT_DIR / ".venv"
RUNTIME_DIR = PROJECT_DIR / ".runtime"


REQUIRED_IMPORTS = [
    ("numpy", "NumPy"),
    ("pandas", "pandas"),
    ("scipy", "SciPy"),
    ("tqdm", "tqdm"),
    ("yaml", "PyYAML"),
    ("pyarrow", "PyArrow"),
    ("dask", "Dask"),
]


def read_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8", errors="replace").strip() or "unknown"
    except Exception:
        return "unknown"


def status_line(ok: bool, label: str, detail: str = "") -> None:
    prefix = "[ OK ]" if ok else "[FAIL]"
    if detail:
        print(f"{prefix} {label}: {detail}")
    else:
        print(f"{prefix} {label}")


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


def check_package_version() -> bool:
    expected = read_version()
    try:
        installed = importlib.metadata.version("photo-cat")
    except importlib.metadata.PackageNotFoundError:
        status_line(False, "PHOTO-CAT package", "not installed in this environment")
        return False

    ok = (installed == expected)
    detail = f"installed {installed}, expected {expected}"
    status_line(ok, "PHOTO-CAT package", detail)
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


def check_project_files() -> bool:
    checks = [
        ("Project folder", PROJECT_DIR.is_dir(), str(PROJECT_DIR)),
        ("config.yaml", CONFIG_PATH.is_file(), str(CONFIG_PATH)),
        ("VERSION", VERSION_FILE.is_file(), str(VERSION_FILE)),
        (".venv", VENV_DIR.is_dir(), str(VENV_DIR)),
    ]

    runtime_detail = str(RUNTIME_DIR) if RUNTIME_DIR.exists() else "not present, only needed when no suitable system Python exists"
    checks.append((".runtime", True, runtime_detail))

    all_ok = True
    for label, ok, detail in checks:
        status_line(ok, label, detail)
        all_ok = all_ok and ok

    return all_ok


def main() -> int:
    print("PHOTO-CAT environment check")
    print("=" * 72)

    checks = [
        check_python_version(),
        check_tkinter(),
        check_package_version(),
        check_imports(),
        check_project_files(),
    ]

    print("=" * 72)

    if all(checks):
        print("PHOTO-CAT environment looks ready.")
        return 0

    print("PHOTO-CAT environment check found issues.")
    print("Run START_WINDOWS.bat or START_UNIX.sh again to repair the local environment.")
    return 1


if (__name__ == "__main__"):
    raise SystemExit(main())
