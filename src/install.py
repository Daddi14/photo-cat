#!/usr/bin/env python3
"""
Create a local virtual environment and install all required libraries.

This file intentionally uses only the Python standard library so it can run
before the project dependencies are installed.
"""

import ctypes
import os
import re
import subprocess
import time
import sys
import venv
import shutil
from datetime import datetime
from pathlib import Path


MINIMUM_PYTHON_VERSION = (3, 10)
PROJECT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = PROJECT_DIR / "VERSION"
VENV_DIR = PROJECT_DIR / ".venv"
VENV_PROJECT_MARKER_FILE = VENV_DIR / ".photo_cat_project_dir"
REQUIREMENTS_FILE = PROJECT_DIR / "requirements.txt"
LOG_DIR = PROJECT_DIR / "logs"
INSTALL_LOG_FILE = LOG_DIR / "install.log"

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


RULE_WIDTH = 72
INFO_LABEL_WIDTH = 20


def write_rule(style: str = Style.CYAN, char: str = "-") -> None:
    print(color(char * RULE_WIDTH, style))


def write_title_rule(style: str = Style.CYAN) -> None:
    print(color("=" * RULE_WIDTH, style))


def write_info_line(label: str, value: object) -> None:
    print(f"  {label:<{INFO_LABEL_WIDTH}}: {value}")


def write_note(message: str) -> None:
    print(color(f"  {message}", Style.DIM))


def write_step(index: int, total: int, message: str) -> None:
    print()
    print(color(f"Step {index} of {total} - {message}", Style.CYAN))
    write_rule(Style.GRAY)


def write_ok(message: str) -> None:
    print(color(f"[ OK ] {message}", Style.GREEN))


def write_warn(message: str) -> None:
    print(color(f"[WARN] {message}", Style.YELLOW))


def write_error(message: str) -> None:
    print(color(f"[ERROR] {message}", Style.RED))


def write_progress_suffix(suffix: str) -> None:
    if (not suffix):
        return

    # Keep counters such as "3/3" and "7/7" in the default console color,
    # but render the processed package/task name in grey for consistency with
    # the pipeline progress bars.
    match = re.match(r"^(?:(?P<spinner>[-\\|/])\s+)?(?P<count>\d+/\d+)(?P<rest>\s+\[.*\])$", suffix)
    if (match):
        spinner = match.group("spinner")
        count = match.group("count")
        rest = match.group("rest")

        if (spinner):
            sys.stdout.write(color(f"  {spinner}", Style.GRAY))
            sys.stdout.write(f"  {count}")
        else:
            sys.stdout.write(f"  {count}")

        sys.stdout.write(color(rest, Style.GRAY))
        return

    sys.stdout.write(color(f"  {suffix}", Style.GRAY))


def progress_bar(percent: int, detail: str = "", spinner: str = "", complete: bool = False, width: int = 34) -> None:
    percent = max(0, min(int(percent), 100))

    terminal_width = shutil.get_terminal_size((88, 20)).columns
    max_width = max(42, min(terminal_width - 1, 96))

    prefix = "    "
    percent_text = f"{percent:3d}%"

    suffix_parts = []
    if (spinner):
        suffix_parts.append(str(spinner))
    if (detail):
        suffix_parts.append(str(detail))
    suffix = "  ".join(suffix_parts)

    min_bar_width = 10
    max_bar_width = min(width, 34)
    reserved = len(prefix) + len(percent_text) + 4

    max_suffix_len = max(0, max_width - reserved - min_bar_width - 2)
    if (len(suffix) > max_suffix_len):
        suffix = suffix[:max(0, max_suffix_len - 1)] + "." if (max_suffix_len > 1) else ""

    bar_width = max_width - reserved - len(suffix)
    if (suffix):
        bar_width -= 2
    bar_width = max(min_bar_width, min(max_bar_width, bar_width))

    filled = int(round(bar_width * (percent / 100.0)))
    empty = bar_width - filled

    filled_part = "=" * filled
    empty_part = "-" * empty

    # Clear the current console line before rewriting it. The line is also
    # kept short enough to avoid wrapping when the user resizes the window.
    if (USE_COLOR):
        sys.stdout.write("\r\033[2K")
    else:
        sys.stdout.write("\r" + (" " * max_width) + "\r")

    sys.stdout.write(prefix)
    if (filled_part):
        sys.stdout.write(color(filled_part, Style.MAGENTA))
    if (empty_part):
        sys.stdout.write(color(empty_part, Style.GRAY))
    sys.stdout.write("  ")
    sys.stdout.write(color(percent_text, Style.GREEN))
    if (suffix):
        write_progress_suffix(suffix)
    sys.stdout.flush()

    if (complete):
        sys.stdout.write("\n")
        sys.stdout.flush()


def venv_python_path() -> Path:
    if (os.name == "nt"):
        return (VENV_DIR / "Scripts" / "python.exe")

    return (VENV_DIR / "bin" / "python")


def normalized_path_text(path: Path) -> str:
    try:
        text = str(path.resolve())
    except Exception:
        text = str(path.absolute())

    text = text.replace("\\", "/").rstrip("/")

    if (os.name == "nt"):
        text = text.casefold()

    return text


def normalized_reference_text(text: str) -> str:
    normalized = str(text).strip().strip("'\"").replace("\\", "/").rstrip("/")

    if (os.name == "nt"):
        normalized = normalized.casefold()

    return normalized


def read_stored_project_dir() -> str:
    if (not VENV_PROJECT_MARKER_FILE.is_file()):
        return ""

    try:
        return VENV_PROJECT_MARKER_FILE.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def write_stored_project_dir() -> None:
    VENV_PROJECT_MARKER_FILE.write_text(str(PROJECT_DIR.resolve()) + "\n", encoding="utf-8")


def extract_venv_path_references(text: str) -> list[str]:
    references: list[str] = []
    quoted_patterns = [
        r"['\"]([A-Za-z]:[\\/][^\r\n'\"]*?\.venv)['\"]",
        r"['\"](/[^\r\n'\"]*?\.venv)['\"]",
    ]
    unquoted_patterns = [
        r"[A-Za-z]:[\\/][^\s\r\n'\"]*?\.venv",
        r"/[^\s\r\n'\"]*?\.venv",
    ]

    for pattern in quoted_patterns:
        for match in re.finditer(pattern, text):
            reference = match.group(1).strip()
            if ((reference) and (reference not in references)):
                references.append(reference)

    unquoted_text = re.sub(r"(['\"]).*?\1", " ", text)

    for pattern in unquoted_patterns:
        for match in re.finditer(pattern, unquoted_text):
            reference = match.group(0).strip()
            if ((reference) and (reference not in references)):
                references.append(reference)

    return references


def find_different_embedded_venv_path() -> str:
    candidate_files = [
        VENV_DIR / "pyvenv.cfg",
        VENV_DIR / "bin" / "activate",
        VENV_DIR / "bin" / "activate.csh",
        VENV_DIR / "bin" / "activate.fish",
        VENV_DIR / "bin" / "pip",
        VENV_DIR / "bin" / "pip3",
        VENV_DIR / "Scripts" / "activate",
        VENV_DIR / "Scripts" / "activate.bat",
        VENV_DIR / "Scripts" / "Activate.ps1",
        VENV_DIR / "Scripts" / "pip-script.py",
    ]

    current_venv = normalized_path_text(VENV_DIR)

    for candidate_file in candidate_files:
        if (not candidate_file.is_file()):
            continue

        try:
            file_text = candidate_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for reference in extract_venv_path_references(file_text):
            if (normalized_reference_text(reference) != current_venv):
                return reference

    return ""


def venv_python_health_failure() -> str:
    python_exe = venv_python_path()
    if (not python_exe.is_file()):
        return "the virtual environment Python executable is missing"

    try:
        process = subprocess.run(
            [str(python_exe), "-c", "import sys; print(sys.executable)"],
            cwd=PROJECT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=15,
        )
    except Exception as exc:
        append_log("Virtual environment Python health check failed before it could run.")
        append_log(f"Details: {exc}")
        append_log("")
        return "the virtual environment Python executable could not be started"

    if (process.stdout):
        append_log("Virtual environment Python health check output:")
        append_log(process.stdout.rstrip())

    append_log(f"Virtual environment Python health check exit code: {process.returncode}")
    append_log("")

    if (process.returncode != 0):
        return "the virtual environment Python executable is broken or points to a removed Python installation"

    return ""


def virtual_environment_rebuild_reason() -> str:
    if (not VENV_DIR.exists()):
        return ""

    if (not VENV_DIR.is_dir()):
        return f"{VENV_DIR} exists but is not a folder"

    stored_project_dir = read_stored_project_dir()
    if (stored_project_dir):
        if (normalized_reference_text(stored_project_dir) != normalized_path_text(PROJECT_DIR)):
            return f"PHOTO-CAT was moved from {stored_project_dir} to {PROJECT_DIR}"
    else:
        embedded_venv_path = find_different_embedded_venv_path()
        if (embedded_venv_path):
            return f"the existing virtual environment still points to {embedded_venv_path}"

    python_health_failure = venv_python_health_failure()
    if (python_health_failure):
        return python_health_failure

    return ""


def rebuild_virtual_environment(reason: str) -> bool:
    write_warn("The existing .venv needs to be rebuilt.")
    print(f"  Reason: {reason}")
    write_note("PHOTO-CAT will recreate .venv now. Dependencies may be downloaded again.")
    append_log(f"Rebuilding virtual environment: {reason}")

    try:
        shutil.rmtree(VENV_DIR)
    except Exception as exc:
        write_error("Could not remove the old .venv folder.")
        print(f"Details: {exc}")
        append_log(f"ERROR: could not remove old .venv: {exc}")
        return False

    write_ok("Old virtual environment removed.")
    return True


def reset_log_file() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    with INSTALL_LOG_FILE.open("w", encoding="utf-8", errors="replace") as log_file:
        log_file.write("PHOTO-CAT dependency setup log\n")
        log_file.write(f"Started: {datetime.now().isoformat(timespec='seconds')}\n")
        log_file.write(f"Version: {PROGRAM_VERSION}\n")
        log_file.write(f"Project folder: {PROJECT_DIR}\n")
        log_file.write(f"Virtual environment: {VENV_DIR}\n")
        log_file.write("\n")


def append_log(message: str) -> None:
    with INSTALL_LOG_FILE.open("a", encoding="utf-8", errors="replace") as log_file:
        log_file.write(message)
        if (not message.endswith("\n")):
            log_file.write("\n")


def tail_log(max_lines: int = 40) -> list[str]:
    if (not INSTALL_LOG_FILE.is_file()):
        return []

    lines = INSTALL_LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max_lines:]


def run_logged(command: list[str], description: str) -> bool:
    append_log("=" * 80)
    append_log(description)
    append_log("> " + " ".join(str(part) for part in command))
    append_log("=" * 80)

    with INSTALL_LOG_FILE.open("a", encoding="utf-8", errors="replace") as log_file:
        process = subprocess.run(
            command,
            cwd=PROJECT_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

    append_log("")
    append_log(f"Exit code: {process.returncode}")
    append_log("")

    return (process.returncode == 0)


def run_logged_with_progress(
    command: list[str],
    description: str,
    start_percent: int,
    end_percent: int,
    detail: str,
    complete: bool = False,
) -> bool:
    append_log("=" * 80)
    append_log(description)
    append_log("> " + " ".join(str(part) for part in command))
    append_log("=" * 80)

    spinner_frames = ["-", "\\", "|", "/"]
    start_percent = max(0, min(int(start_percent), 100))
    end_percent = max(start_percent, min(int(end_percent), 100))
    span = max(1, end_percent - start_percent)

    with INSTALL_LOG_FILE.open("a", encoding="utf-8", errors="replace") as log_file:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_DIR,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )

        frame_index = 0
        started_at = time.monotonic()
        while (process.poll() is None):
            elapsed = time.monotonic() - started_at
            animated_percent = start_percent + min(span - 1, int(elapsed * max(4, span / 2)))
            progress_bar(animated_percent, detail, spinner_frames[frame_index % len(spinner_frames)])
            frame_index += 1
            time.sleep(0.12)

        exit_code = int(process.returncode or 0)

    append_log("")
    append_log(f"Exit code: {exit_code}")
    append_log("")

    if (exit_code == 0):
        progress_bar(end_percent, detail, complete=complete)
        return True

    sys.stdout.write("\n")
    sys.stdout.flush()
    return False

def print_failure_details() -> None:
    write_error("Dependency installation failed.")
    print(f"Detailed log: {INSTALL_LOG_FILE}")

    log_tail = tail_log()
    if (log_tail):
        print()
        print(color("Last log lines:", Style.YELLOW))
        print("-" * 64)
        for line in log_tail:
            print(line)
        print("-" * 64)


def read_requirements() -> list[str]:
    requirements: list[str] = []

    for raw_line in REQUIREMENTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()

        if ((not line) or line.startswith("#")):
            continue

        requirements.append(line)

    return requirements


def display_requirement_name(requirement: str) -> str:
    cleaned = requirement.split(";", 1)[0].strip()
    cleaned = re.split(r"[<>=!~]", cleaned, maxsplit=1)[0].strip()
    return (cleaned or requirement)


def requirements_are_satisfied(python_exe: Path, requirements: list[str]) -> bool:
    helper_code = r'''
import importlib.metadata
import sys

try:
    from pip._vendor.packaging.requirements import Requirement
except Exception as exc:
    print(f"Could not load requirement parser: {exc}")
    raise SystemExit(1)

missing = []

for raw_requirement in sys.argv[1:]:
    try:
        requirement = Requirement(raw_requirement)

        if ((requirement.marker is not None) and (not requirement.marker.evaluate())):
            continue

        if (requirement.url):
            missing.append(raw_requirement)
            continue

        installed_version = importlib.metadata.version(requirement.name)

        if ((requirement.specifier) and (installed_version not in requirement.specifier)):
            missing.append(f"{raw_requirement} (installed: {installed_version})")
    except Exception as exc:
        missing.append(f"{raw_requirement} ({exc})")

if (missing):
    print("Missing or outdated requirements:")
    for requirement in missing:
        print(f"- {requirement}")
    raise SystemExit(1)

raise SystemExit(0)
'''

    append_log("=" * 80)
    append_log("Checking installed requirements")
    append_log("=" * 80)

    process = subprocess.run(
        [str(python_exe), "-c", helper_code, *requirements],
        cwd=PROJECT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if (process.stdout):
        append_log(process.stdout.rstrip())

    append_log(f"Exit code: {process.returncode}")
    append_log("")

    return (process.returncode == 0)


def show_dependency_check_progress(requirements: list[str]) -> None:
    total = max(1, len(requirements))

    for index, requirement in enumerate(requirements, start=1):
        package_name = display_requirement_name(requirement)
        percent = int(round((index / total) * 100.0))
        detail = f"{index}/{total} [{package_name}]"
        progress_bar(percent, detail, complete=(index == total))


def install_packages_one_by_one(python_exe: Path, requirements: list[str]) -> bool:
    total = len(requirements)

    for index, requirement in enumerate(requirements, start=1):
        package_name = display_requirement_name(requirement)
        start_percent = int(round(((index - 1) / total) * 100.0))
        end_percent = int(round((index / total) * 100.0))
        detail = f"{index}/{total} [{package_name}]"

        if (not run_logged_with_progress(
            [
                str(python_exe),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                requirement,
            ],
            f"Installing dependency: {requirement}",
            start_percent,
            end_percent,
            detail,
            complete=(index == total),
        )):
            print_failure_details()
            return False

    return True


def main() -> int:
    enable_windows_ansi()
    reset_log_file()

    if (sys.version_info < MINIMUM_PYTHON_VERSION):
        current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        required_version = f"{MINIMUM_PYTHON_VERSION[0]}.{MINIMUM_PYTHON_VERSION[1]}"
        write_error(f"Python {required_version} or newer is required. You are using Python {current_version}.")
        print("Install Python from https://www.python.org/downloads/ and run this again.")
        return 1

    if (not REQUIREMENTS_FILE.is_file()):
        write_error(f"requirements.txt was not found here: {REQUIREMENTS_FILE}")
        return 1

    write_step(1, 3, "Prepare local environment")
    progress_bar(0, "[virtual environment]")

    rebuild_reason = virtual_environment_rebuild_reason()
    if (rebuild_reason):
        sys.stdout.write("\n")
        sys.stdout.flush()
        if (not rebuild_virtual_environment(rebuild_reason)):
            return 1
        progress_bar(0, "[virtual environment]")

    if (not VENV_DIR.exists()):
        try:
            venv.create(VENV_DIR, with_pip=True)
        except Exception as exc:
            write_error("Could not create the virtual environment.")
            print("On Linux, you may need to install the python3-venv package first.")
            print(f"Details: {exc}")
            append_log(f"ERROR: could not create virtual environment: {exc}")
            return 1

        progress_bar(100, "[virtual environment]", complete=True)
        write_ok("Virtual environment created.")
    else:
        progress_bar(100, "[virtual environment]", complete=True)
        write_ok("Virtual environment already exists. Reusing it.")

    python_exe = venv_python_path()
    if (not python_exe.is_file()):
        write_error(f"Could not find the virtual environment Python here: {python_exe}")
        print("Delete the .venv folder and run the installer again.")
        return 1

    try:
        write_stored_project_dir()
    except Exception as exc:
        write_warn(f"Could not save the .venv path marker: {exc}")
        append_log(f"WARNING: could not save .venv path marker: {exc}")

    write_step(2, 3, "Verify installation tools")
    tools = ["pip", "setuptools", "wheel"]
    for index, tool_name in enumerate(tools, start=1):
        start_percent = int(round(((index - 1) / len(tools)) * 100.0))
        end_percent = int(round((index / len(tools)) * 100.0))
        detail = f"{index}/{len(tools)} [{tool_name}]"

        if (not run_logged_with_progress(
            [
                str(python_exe),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--upgrade",
                tool_name,
            ],
            f"Upgrading {tool_name}",
            start_percent,
            end_percent,
            detail,
            complete=(index == len(tools)),
        )):
            print_failure_details()
            return 1

    write_ok("Installation tools are ready.")

    requirements = read_requirements()
    if (not requirements):
        write_error("requirements.txt is empty. There are no dependencies to install.")
        return 1

    dependencies_ready = requirements_are_satisfied(python_exe, requirements)
    if (dependencies_ready):
        write_step(3, 3, "Verify project dependencies")
        write_note("All required dependencies are already available.")
        show_dependency_check_progress(requirements)
        write_ok("Dependencies are ready.")
    else:
        write_step(3, 3, "Install project dependencies")
        write_note("This may take a few minutes on the first run.")

        if (not install_packages_one_by_one(python_exe, requirements)):
            return 1

        write_ok("Dependencies installed successfully.")

    print()
    write_title_rule(Style.GREEN)
    print(color("PHOTO-CAT setup is complete.", Style.BOLD + Style.GREEN))
    print(color("The local environment is ready to use.", Style.GREEN))
    write_title_rule(Style.GREEN)
    print()
    write_info_line("Detailed install log", INSTALL_LOG_FILE)
    print()
    return 0


if (__name__ == "__main__"):
    raise SystemExit(main())
