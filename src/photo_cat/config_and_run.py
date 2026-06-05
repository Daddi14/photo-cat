#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""
Run the full photometric contamination pipeline from config.yaml.

Pipeline:
  1. build_neighbors_index.py
  2. query_contamination_from_index.py
"""

import ctypes
import os
import subprocess
import sys
from pathlib import Path

import yaml

from .logger_setup import get_logger


logger = get_logger(__name__)
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_DIR = SRC_DIR.parent
CONFIG_PATH = Path(os.environ.get("PHOTO_CAT_CONFIG", str(PROJECT_DIR / "config.yaml"))).resolve()
VERSION_FILE = PROJECT_DIR / "VERSION"
RULE_WIDTH = 72
INFO_LABEL_WIDTH = 18

try:
    PROGRAM_VERSION = VERSION_FILE.read_text(encoding="utf-8", errors="replace").strip() or "unknown"
except Exception:
    PROGRAM_VERSION = "unknown"


class Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"


def enable_windows_ansi() -> None:
    if (os.name != "nt"):
        return

    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()

        if (kernel32.GetConsoleMode(handle, ctypes.byref(mode))):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def supports_color() -> bool:
    if (os.environ.get("NO_COLOR")):
        return False

    return sys.stdout.isatty()


USE_COLOR = supports_color()


def color(text: str, style: str) -> str:
    if (not USE_COLOR):
        return text

    return f"{style}{text}{Style.RESET}"


def write_rule(style: str = Style.CYAN) -> None:
    print(color("=" * RULE_WIDTH, style))


def write_soft_rule() -> None:
    print(color("-" * RULE_WIDTH, Style.GRAY))


def write_info_line(label: str, value: object) -> None:
    print(f"  {label:<{INFO_LABEL_WIDTH}}: {value}")


def write_header(title: str) -> None:
    write_rule(Style.CYAN)
    print(color(title, Style.BOLD + Style.CYAN))
    write_rule(Style.CYAN)
    print()
    write_info_line("Version", PROGRAM_VERSION)
    write_info_line("Project folder", PROJECT_DIR)
    write_info_line("Configuration", CONFIG_PATH)
    print()


def write_step(index: int, total: int, message: str) -> None:
    print()
    print(color(f"Step {index} of {total} - {message}", Style.CYAN))
    write_soft_rule()


def write_success(message: str) -> None:
    print(color(message, Style.GREEN))


def write_success_summary() -> None:
    print()
    write_rule(Style.GREEN)
    print(color("PHOTO-CAT pipeline is complete.", Style.BOLD + Style.GREEN))
    print(color("Check the output folder for results.", Style.GREEN))
    write_rule(Style.GREEN)
    print()


def compact_environment() -> dict:
    env = {**os.environ}
    env.pop("NO_COLOR", None)
    env.setdefault("PHOTO_CAT_COMPACT_LOG", "1")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_DIR) if (not existing_pythonpath) else str(SRC_DIR) + os.pathsep + existing_pythonpath
    if (os.name == "nt"):
        env.setdefault("PHOTO_CAT_FORCE_COLOR", "1")
    return env


def load_execution_config() -> dict:
    if (not CONFIG_PATH.is_file()):
        raise FileNotFoundError(f"config.yaml was not found here: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = (yaml.safe_load(f) or {})

    return (config.get("execution", {}) or {})


def run_step(module_name: str, step_index: int, step_total: int, step_title: str, activity_label: str) -> None:
    script_path = PACKAGE_DIR / f"{module_name}.py"

    if (not script_path.is_file()):
        raise FileNotFoundError(f"Required script was not found: {script_path}")

    write_step(step_index, step_total, step_title)

    result = subprocess.run(
        [sys.executable, "-m", f"photo_cat.{module_name}"],
        check=False,
        cwd=PROJECT_DIR,
        env=compact_environment(),
    )

    if (result.returncode != 0):
        raise RuntimeError(
            f"{module_name}.py failed.\n"
            "Read the error message above, fix the configuration in the GUI, then run again."
        )

    print()
    write_success(f"Completed: {activity_label}")


def main() -> int:
    enable_windows_ansi()
    os.chdir(PROJECT_DIR)
    write_header("PHOTO-CAT - Pipeline")

    pipeline_cfg = load_execution_config()
    run_build = bool(pipeline_cfg.get("run_build", True))
    run_query = bool(pipeline_cfg.get("run_query", True))

    if (not run_build and not run_query):
        logger.warning("Both run_build and run_query are false. Nothing to do.")
        return 0

    stage_total = int(run_build) + int(run_query)
    stage_index = 0

    if (run_build):
        stage_index += 1
        run_step(
            "build_neighbors_index",
            stage_index,
            stage_total,
            "Build neighbour index",
            "Build neighbour index",
        )

    if (run_query):
        stage_index += 1
        run_step(
            "query_contamination_from_index",
            stage_index,
            stage_total,
            "Query contamination",
            "Query contamination",
        )

    write_success_summary()
    return 0


if (__name__ == "__main__"):
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.error("Interrupted by user.")
        raise SystemExit(130)
    except Exception as exc:
        logger.error("%s", exc)
        raise SystemExit(1)
