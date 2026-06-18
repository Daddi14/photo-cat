#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Run the configurable PHOTO-CAT build and query pipeline."""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .load_config import EXECUTION_SECTION, ExecutionConfig, load_config, resolve_config_path
from .logger_setup import get_logger


logger = get_logger(__name__)
PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_DIR = SRC_DIR.parent
VERSION_FILE = PROJECT_DIR / "VERSION"
RULE_WIDTH = 72
INFO_LABEL_WIDTH = 18

try:
    PROGRAM_VERSION = VERSION_FILE.read_text(encoding="utf-8", errors="replace").strip() or "unknown"
except Exception:
    PROGRAM_VERSION = "unknown"


@dataclass(frozen=True)
class PipelineStage:
    """One public pipeline stage with its module and display labels."""

    module_name: str
    title: str
    activity_label: str


BUILD_STAGE = PipelineStage("build_neighbors_index", "Build neighbour index", "Build neighbour index")
QUERY_STAGE = PipelineStage("query_contamination_from_index", "Query contamination", "Query contamination")


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
    """Enable ANSI console formatting on supported Windows terminals."""
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
    """Return whether this invocation should emit ANSI colour codes."""
    if (os.environ.get("NO_COLOR")):
        return False

    return sys.stdout.isatty()


USE_COLOR = supports_color()


def color(text: str, style: str) -> str:
    """Apply a terminal style only when colour output is supported."""
    if (not USE_COLOR):
        return text

    return f"{style}{text}{Style.RESET}"


def write_rule(style: str = Style.CYAN) -> None:
    """Write one visual rule in terminal output."""
    print(color("=" * RULE_WIDTH, style))


def write_soft_rule() -> None:
    """Write one subdued terminal rule."""
    print(color("-" * RULE_WIDTH, Style.GRAY))


def write_info_line(label: str, value: object) -> None:
    """Write one aligned pipeline-information line."""
    print(f"  {label:<{INFO_LABEL_WIDTH}}: {value}")


def write_header(title: str, config_path: Path) -> None:
    """Print the pipeline header without loading or mutating configuration."""
    write_rule(Style.CYAN)
    print(color(title, Style.BOLD + Style.CYAN))
    write_rule(Style.CYAN)
    print()
    write_info_line("Version", PROGRAM_VERSION)
    write_info_line("Project folder", PROJECT_DIR)
    write_info_line("Configuration", config_path)
    print()


def write_step(index: int, total: int, message: str) -> None:
    """Write a numbered pipeline-stage heading."""
    print()
    print(color(f"Step {index} of {total} - {message}", Style.CYAN))
    write_soft_rule()


def write_success(message: str) -> None:
    """Write a successful stage message."""
    print(color(message, Style.GREEN))


def write_success_summary() -> None:
    """Write the pipeline completion summary."""
    print()
    write_rule(Style.GREEN)
    print(color("PHOTO-CAT pipeline is complete.", Style.BOLD + Style.GREEN))
    print(color("Check the output folder for results.", Style.GREEN))
    write_rule(Style.GREEN)
    print()


def compact_environment(config_path: Path | None = None) -> dict[str, str]:
    """Build a child-process environment without mutating the parent process."""
    env = {**os.environ}
    env.pop("NO_COLOR", None)
    env.setdefault("PHOTO_CAT_COMPACT_LOG", "1")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(SRC_DIR) if (not existing_pythonpath) else str(SRC_DIR) + os.pathsep + existing_pythonpath

    if (config_path is not None):
        env["PHOTO_CAT_CONFIG"] = str(config_path)

    if (os.name == "nt"):
        env.setdefault("PHOTO_CAT_FORCE_COLOR", "1")

    return env


def resolve_pipeline_stages(config: ExecutionConfig) -> list[PipelineStage]:
    """Translate execution configuration into the ordered pipeline plan."""
    stages: list[PipelineStage] = []

    if (config.run_build):
        stages.append(BUILD_STAGE)

    if (config.run_query):
        stages.append(QUERY_STAGE)

    return stages


def run_stage(
    stage: PipelineStage,
    step_index: int,
    step_total: int,
    config_path: Path | None = None,
) -> None:
    """Execute one stage in a child process with an explicit configuration context."""
    script_path = PACKAGE_DIR / f"{stage.module_name}.py"
    if (not script_path.is_file()):
        raise FileNotFoundError(f"Required script was not found: {script_path}")

    write_step(step_index, step_total, stage.title)

    result = subprocess.run(
        [sys.executable, "-m", f"photo_cat.{stage.module_name}"],
        check=False,
        cwd=PROJECT_DIR,
        env=compact_environment(config_path),
    )

    if (result.returncode != 0):
        raise RuntimeError(
            f"{stage.module_name}.py failed.\n"
            "Read the error message above, fix the configuration in the GUI, then run again."
        )

    print()
    write_success(f"Completed: {stage.activity_label}")


def run_pipeline_stages(
    stages: list[PipelineStage],
    runner: Callable[[PipelineStage, int, int], None] = run_stage,
) -> None:
    """Run an already-resolved pipeline plan with an injectable stage runner."""
    total = len(stages)
    for index, stage in enumerate(stages, start=1):
        runner(stage, index, total)


def run_configured_pipeline(stages: list[PipelineStage], config_path: Path) -> None:
    """Run stages while scoping the resolved config path to child process environments."""
    run_pipeline_stages(
        stages,
        lambda stage, index, total: run_stage(stage, index, total, config_path),
    )


def main(config_path: str | Path | None = None) -> int:
    """Load an execution plan and orchestrate stages without changing process cwd or env."""
    enable_windows_ansi()

    resolved_config_path = resolve_config_path(config_path)
    execution_config = load_config(EXECUTION_SECTION, resolved_config_path)
    if (not isinstance(execution_config, ExecutionConfig)):
        raise RuntimeError("Failed to load execution configuration.")

    stages = resolve_pipeline_stages(execution_config)
    write_header("PHOTO-CAT - Pipeline", resolved_config_path)

    if (not stages):
        logger.warning("Both run_build and run_query are false. Nothing to do.")
        return 0

    run_configured_pipeline(stages, resolved_config_path)
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
