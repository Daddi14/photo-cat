#!/usr/bin/env python3
"""
Create a local virtual environment and install all required libraries.

This file intentionally uses only the Python standard library so it can run
before the project dependencies are installed.
"""

import os
import subprocess
import sys
import venv
from pathlib import Path


MINIMUM_PYTHON_VERSION = (3, 10)
PROJECT_DIR = Path(__file__).resolve().parent.parent
VENV_DIR = PROJECT_DIR / ".venv"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"


def venv_python_path() -> Path:
    if (os.name == "nt"):
        return (VENV_DIR / "Scripts" / "python.exe")

    return (VENV_DIR / "bin" / "python")


def run_command(command: list[str]) -> None:
    print()
    print("> " + " ".join(str(part) for part in command))
    subprocess.check_call(command, cwd=PROJECT_DIR)


def main() -> int:
    if (sys.version_info < MINIMUM_PYTHON_VERSION):
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        required_version = f"{MINIMUM_PYTHON_VERSION[0]}.{MINIMUM_PYTHON_VERSION[1]}"
        print(f"ERROR: Python {required_version} or newer is required. You are using Python {current_version}.")
        print("Install Python from https://www.python.org/downloads/ and run this again.")
        return 1

    if (not REQUIREMENTS_FILE.is_file()):
        print(f"ERROR: requirements.txt was not found here: {REQUIREMENTS_FILE}")
        return 1

    print("============================================================")
    print("PHOTO-CAT - dependency installation")
    print("============================================================")
    print(f"Project folder: {PROJECT_DIR}")
    print(f"Virtual environment: {VENV_DIR}")

    if (not VENV_DIR.exists()):
        print()
        print("[1/3] Creating the local virtual environment...")
        try:
            venv.create(VENV_DIR, with_pip=True)
        except Exception as exc:
            print()
            print("ERROR: Could not create the virtual environment.")
            print("On Linux, you may need to install the python3-venv package first.")
            print(f"Details: {exc}")
            return 1
    else:
        print()
        print("[1/3] Virtual environment already exists. Reusing it.")

    python_exe = venv_python_path()
    if (not python_exe.is_file()):
        print(f"ERROR: Could not find the virtual environment Python here: {python_exe}")
        print("Delete the .venv folder and run the installer again.")
        return 1

    print()
    print("[2/3] Upgrading pip/setuptools/wheel...")
    run_command([str(python_exe), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"])

    print()
    print("[3/3] Installing project libraries from requirements.txt...")
    run_command([str(python_exe), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])

    print()
    print("============================================================")
    print("Installation completed successfully.")
    print("Next steps:")
    print("1. Run your operating-system starter again and configure your catalog/targets.")
    print("2. Click Save + run in the configurator, or run the starter again later.")
    print("============================================================")
    return 0


if (__name__ == "__main__"):
    raise SystemExit(main())
