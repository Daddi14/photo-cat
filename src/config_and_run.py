#!/usr/bin/env python3
"""
Run the full photometric contamination pipeline from config.yaml.

Pipeline:
  1. build_neighbors_index.py
  2. query_contamination_from_index.py
"""

import os
import subprocess
import sys
from pathlib import Path

import yaml

from logger_setup import get_logger


logger = get_logger(__name__)
SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent
CONFIG_PATH = PROJECT_DIR / "config.yaml"


def load_execution_config() -> dict:
    if (not CONFIG_PATH.is_file()):
        raise FileNotFoundError(f"config.yaml was not found here: {CONFIG_PATH}")

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = (yaml.safe_load(f) or {})

    return (config.get("execution", {}) or {})


def run_step(script_name: str) -> None:
    script_path = SRC_DIR / script_name

    if (not script_path.is_file()):
        raise FileNotFoundError(f"Required script was not found: {script_path}")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        check=False,
        cwd=PROJECT_DIR,
        env={**os.environ},
    )

    if (result.returncode != 0):
        raise RuntimeError(
            f"{script_name} failed.\n"
            "Read the error message above, fix the configuration in the GUI, then run again."
        )


def main() -> int:
    os.chdir(PROJECT_DIR)

    pipeline_cfg = load_execution_config()
    run_build = bool(pipeline_cfg.get("run_build", True))
    run_query = bool(pipeline_cfg.get("run_query", True))

    if (not run_build and not run_query):
        logger.warning("Both run_build and run_query are false. Nothing to do.")
        return 0

    if (run_build):
        logger.info("=== Running build_neighbors_index.py ===")
        run_step("build_neighbors_index.py")

    if (run_query):
        logger.info("=== Running query_contamination_from_index.py ===")
        run_step("query_contamination_from_index.py")

    logger.info("Pipeline completed successfully.")
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
