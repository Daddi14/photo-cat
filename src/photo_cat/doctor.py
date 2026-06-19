#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""PHOTO-CAT environment self-check with optional machine-readable output."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


PACKAGE_NAME = "photo-cat"
DOCTOR_SCHEMA_VERSION = 1

REQUIRED_IMPORTS = [
    ("numpy", "NumPy"),
    ("pandas", "pandas"),
    ("scipy", "SciPy"),
    ("tqdm", "tqdm"),
    ("yaml", "PyYAML"),
    ("pyarrow", "PyArrow"),
    ("dask", "Dask"),
]

DiagnosticStatus = Literal["pass", "warn", "fail", "info"]


@dataclass(frozen=True)
class DiagnosticCheck:
    """One stable doctor diagnostic suitable for text and JSON rendering."""

    name: str
    status: DiagnosticStatus
    message: str
    detail: str = ""


class DoctorReporter:
    """Collect doctor checks and render text immediately when requested."""

    def __init__(self, output_format: str = "text") -> None:
        self.output_format = output_format
        self.checks: list[DiagnosticCheck] = []

    def add(self, name: str, status: DiagnosticStatus, message: str, detail: str = "") -> None:
        check = DiagnosticCheck(name=name, status=status, message=message, detail=detail)
        self.checks.append(check)

        if (self.output_format == "text"):
            render_text_check(check)

    def status(self, name: str, label: str, ok: bool, detail: str = "") -> bool:
        self.add(name, "pass" if ok else "fail", label, detail)
        return ok

    def warning(self, name: str, label: str, detail: str = "") -> None:
        self.add(name, "warn", label, detail)

    def info(self, name: str, label: str, detail: str = "") -> None:
        self.add(name, "info", label, detail)

    def payload(self) -> dict[str, object]:
        summary = {
            "passed": sum(check.status == "pass" for check in self.checks),
            "warnings": sum(check.status == "warn" for check in self.checks),
            "failed": sum(check.status == "fail" for check in self.checks),
            "information": sum(check.status == "info" for check in self.checks),
        }

        return {
            "schema_version": DOCTOR_SCHEMA_VERSION,
            "ok": summary["failed"] == 0,
            "checks": [asdict(check) for check in self.checks],
            "summary": summary,
        }


def render_text_check(check: DiagnosticCheck) -> None:
    """Render one diagnostic using the established human-readable doctor style."""
    prefixes = {
        "pass": "[ OK ]",
        "warn": "[WARN]",
        "fail": "[FAIL]",
        "info": "[INFO]",
    }
    prefix = prefixes[check.status]

    if (check.detail):
        print(f"{prefix} {check.message}: {check.detail}")
    else:
        print(f"{prefix} {check.message}")


def status_line(ok: bool, label: str, detail: str = "") -> None:
    """Preserve the legacy text helper for direct callers and older tests."""
    render_text_check(DiagnosticCheck("legacy", "pass" if ok else "fail", label, detail))


def warning_line(label: str, detail: str = "") -> None:
    """Render one recoverable diagnostic in the legacy text format."""
    render_text_check(DiagnosticCheck("legacy", "warn", label, detail))


def info_line(label: str, detail: str = "") -> None:
    """Preserve the legacy text helper for direct callers and older tests."""
    render_text_check(DiagnosticCheck("legacy", "info", label, detail))


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


def project_venv_python_path(venv_dir: Path) -> Path:
    """Return the expected platform-specific Python executable inside a local venv."""
    if (os.name == "nt"):
        return venv_dir / "Scripts" / "python.exe"

    return venv_dir / "bin" / "python"


def read_venv_project_marker(venv_dir: Path) -> str:
    """Read PHOTO-CAT's optional venv project-location marker without raising."""
    marker_path = venv_dir / ".photo_cat_project_dir"

    try:
        return marker_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def normalize_path_text(value: str | Path) -> str:
    """Normalize a path for platform-aware stale-venv marker comparison."""
    try:
        text = str(Path(value).resolve())
    except Exception:
        text = str(value)

    text = text.replace("\\", "/").rstrip("/")
    return text.casefold() if (os.name == "nt") else text


def check_python_version(reporter: DoctorReporter | None = None) -> bool:
    version = sys.version_info
    ok = ((version.major, version.minor) >= (3, 10) and (version.major, version.minor) < (3, 14))
    detail = sys.version.split()[0]

    if (reporter is None):
        status_line(ok, "Python", detail)
    else:
        reporter.status("python", "Python", ok, detail)

    return ok


def check_tkinter(reporter: DoctorReporter | None = None) -> bool:
    try:
        import tkinter  # noqa: F401

        if (reporter is None):
            status_line(True, "Tkinter")
        else:
            reporter.status("tkinter", "Tkinter", True)
        return True
    except Exception as exc:
        if (reporter is None):
            status_line(False, "Tkinter", str(exc))
        else:
            reporter.status("tkinter", "Tkinter", False, str(exc))
        return False


def check_package_version(project_dir: Path | None, reporter: DoctorReporter | None = None) -> bool:
    installed = installed_package_version()
    expected = read_project_version(project_dir)

    if (installed is None):
        if (reporter is None):
            status_line(False, "PHOTO-CAT package", "not installed in this environment")
        else:
            reporter.status("photo_cat_package", "PHOTO-CAT package", False, "not installed in this environment")
        return False

    if (expected is None):
        if (reporter is None):
            status_line(True, "PHOTO-CAT package", f"installed {installed}")
        else:
            reporter.status("photo_cat_package", "PHOTO-CAT package", True, f"installed {installed}")
        return True

    ok = (installed == expected)
    detail = f"installed {installed}, expected {expected}"
    if (reporter is None):
        status_line(ok, "PHOTO-CAT package", detail)
    else:
        reporter.status("photo_cat_package", "PHOTO-CAT package", ok, detail)
    return ok


def check_imports(reporter: DoctorReporter | None = None) -> bool:
    all_ok = True

    for module_name, display_name in REQUIRED_IMPORTS:
        try:
            importlib.import_module(module_name)
            if (reporter is None):
                status_line(True, display_name)
            else:
                reporter.status(f"dependency_{module_name.replace('.', '_')}", display_name, True)
        except Exception as exc:
            all_ok = False
            if (reporter is None):
                status_line(False, display_name, str(exc))
            else:
                reporter.status(f"dependency_{module_name.replace('.', '_')}", display_name, False, str(exc))

    return all_ok


def check_project_virtual_environment(project_dir: Path, reporter: DoctorReporter | None = None) -> bool:
    """Report recoverable stale local venv conditions without requiring a rebuild."""
    venv_dir = project_dir / ".venv"

    if (not venv_dir.exists()):
        if (reporter is None):
            info_line(".venv", "not present; run a launcher to create the local environment")
        else:
            reporter.info("project_venv", ".venv", "not present; run a launcher to create the local environment")
        return True

    if (not venv_dir.is_dir()):
        detail = f"{venv_dir} exists but is not a folder"
        if (reporter is None):
            status_line(False, ".venv", detail)
        else:
            reporter.status("project_venv", ".venv", False, detail)
        return False

    stored_project_dir = read_venv_project_marker(venv_dir)
    if (stored_project_dir and normalize_path_text(stored_project_dir) != normalize_path_text(project_dir)):
        detail = f"stale project marker points to {stored_project_dir}; run a launcher to rebuild it"
        if (reporter is None):
            warning_line(".venv", detail)
        else:
            reporter.warning("project_venv", ".venv", detail)
        return True

    pyvenv_config = venv_dir / "pyvenv.cfg"
    python_executable = project_venv_python_path(venv_dir)

    if (not pyvenv_config.is_file()):
        detail = "missing pyvenv.cfg; run a launcher to rebuild it"
        if (reporter is None):
            warning_line(".venv", detail)
        else:
            reporter.warning("project_venv", ".venv", detail)
        return True

    if (not python_executable.is_file()):
        detail = f"missing Python executable at {python_executable}; run a launcher to rebuild it"
        if (reporter is None):
            warning_line(".venv", detail)
        else:
            reporter.warning("project_venv", ".venv", detail)
        return True

    if (reporter is None):
        status_line(True, ".venv", str(venv_dir))
    else:
        reporter.status("project_venv", ".venv", True, str(venv_dir))
    return True


def check_project_context(
    project_dir: Path | None,
    explicit_config_path: str | Path | None = None,
    reporter: DoctorReporter | None = None,
) -> bool:
    """Check project resources with an explicit config selection when supplied."""
    config_path, explicit_config = resolve_config_path(project_dir, explicit_config_path)

    if (project_dir is None):
        if (reporter is None):
            info_line("Project folder", "not checked in package-install mode")
        else:
            reporter.info("project_folder", "Project folder", "not checked in package-install mode")

        if (config_path is None):
            if (reporter is None):
                info_line("config.yaml", "not checked; pass --config when validating a run configuration")
                info_line(".venv", "not checked in package-install mode")
                info_line(".runtime", "not checked in package-install mode")
            else:
                reporter.info("configuration", "config.yaml", "not checked; pass --config when validating a run configuration")
                reporter.info("project_venv", ".venv", "not checked in package-install mode")
                reporter.info("project_runtime", ".runtime", "not checked in package-install mode")
            return True

        ok = config_path.is_file()
        label = "config.yaml"
        if (reporter is None):
            status_line(ok, label, str(config_path))
            info_line(".venv", "not checked in package-install mode")
            info_line(".runtime", "not checked in package-install mode")
        else:
            reporter.status("configuration", label, ok, str(config_path))
            reporter.info("project_venv", ".venv", "not checked in package-install mode")
            reporter.info("project_runtime", ".runtime", "not checked in package-install mode")
        return ok

    if (reporter is None):
        status_line(True, "Project folder", str(project_dir))
    else:
        reporter.status("project_folder", "Project folder", True, str(project_dir))

    version_file = project_dir / "VERSION"
    version_ok = version_file.is_file()
    if (reporter is None):
        status_line(version_ok, "VERSION", str(version_file))
    else:
        reporter.status("project_version", "VERSION", version_ok, str(version_file))

    all_ok = version_ok

    if (config_path is not None):
        config_ok = config_path.is_file()
        label = "config.yaml" if (not explicit_config) else "config"
        if (reporter is None):
            status_line(config_ok, label, str(config_path))
        else:
            reporter.status("configuration", label, config_ok, str(config_path))
        all_ok = all_ok and config_ok

    all_ok = check_project_virtual_environment(project_dir, reporter) and all_ok

    runtime_dir = project_dir / ".runtime"
    runtime_detail = str(runtime_dir) if runtime_dir.exists() else "not present; only needed when no suitable system Python exists"
    if (reporter is None):
        info_line(".runtime", runtime_detail)
    else:
        reporter.info("project_runtime", ".runtime", runtime_detail)

    return all_ok


def emit_json_report(reporter: DoctorReporter) -> None:
    """Write exactly one stable JSON document for automation callers."""
    print(json.dumps(reporter.payload(), ensure_ascii=False, sort_keys=True))


def main(config_path: str | Path | None = None, output_format: str = "text") -> int:
    """Run diagnostics in text or JSON mode without mutating process configuration state."""
    if (output_format not in {"text", "json"}):
        raise ValueError(f"Unsupported doctor output format: {output_format}")

    reporter = DoctorReporter(output_format)
    project_dir = find_project_dir()

    if (output_format == "text"):
        print("PHOTO-CAT environment check")
        print("=" * 72)

    checks = [
        check_python_version(reporter),
        check_tkinter(reporter),
        check_package_version(project_dir, reporter),
        check_imports(reporter),
        check_project_context(project_dir, config_path, reporter),
    ]
    ok = all(checks)

    if (output_format == "json"):
        emit_json_report(reporter)
        return 0 if ok else 1

    print("=" * 72)

    if (ok):
        print("PHOTO-CAT environment looks ready.")
        return 0

    print("PHOTO-CAT environment check found issues.")
    print("Review the failed checks above. If running from a release folder, run START_WINDOWS.bat or START_UNIX.sh again to repair the local environment.")
    return 1


if (__name__ == "__main__"):
    raise SystemExit(main())
