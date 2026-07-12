# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Frozen-build entry point.

PyInstaller freezes this script into ``photo-cat.exe``. It dispatches to the same
CLI as the ``photo-cat`` console script, so ``photo-cat.exe <subcommand>`` works
exactly like the pip-installed command, and ``photo-cat.exe configure`` opens the
GUI configurator.
"""

from __future__ import annotations

import multiprocessing
import sys


def main() -> int:
    from photo_cat.cli import main as cli_main

    return int(cli_main() or 0)


if (__name__ == "__main__"):
    # Required so a frozen build does not re-launch the whole app when libraries
    # (e.g. Dask/loky) start helper processes.
    multiprocessing.freeze_support()
    raise SystemExit(main())
