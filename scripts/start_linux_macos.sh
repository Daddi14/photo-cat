#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1
VERSION_FILE="$PROJECT_DIR/VERSION"
PROGRAM_VERSION="unknown"
if [ -f "$VERSION_FILE" ]; then
    version_text=$(head -n 1 "$VERSION_FILE" 2>/dev/null | tr -d '\r')
    if [ -n "$version_text" ]; then
        PROGRAM_VERSION="$version_text"
    fi
fi
export PHOTO_CAT_PROJECT_DIR="$PROJECT_DIR"
export PHOTO_CAT_CONFIG="$PROJECT_DIR/config.yaml"
export PHOTO_CAT_VERSION="$PROGRAM_VERSION"

MODE="ALL"
case "${1:-}" in
    --install-only)
        MODE="INSTALL"
        ;;
    --configure-only)
        MODE="CONFIGURE"
        ;;
    --run-only)
        MODE="RUN"
        ;;
esac

PYTHON_CMD=""
OS_NAME="$(uname -s 2>/dev/null || echo Unknown)"
LOG_DIR="$PROJECT_DIR/logs"
SETUP_LOG="$LOG_DIR/setup_unix.log"

USE_COLOR=0
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    USE_COLOR=1
fi

RESET=""
BOLD=""
DIM=""
CYAN=""
GREEN=""
YELLOW=""
RED=""
MAGENTA=""
GRAY=""

if [ "$USE_COLOR" -eq 1 ]; then
    RESET="\033[0m"
    BOLD="\033[1m"
    DIM="\033[2m"
    CYAN="\033[36m"
    GREEN="\033[32m"
    YELLOW="\033[33m"
    RED="\033[31m"
    MAGENTA="\033[35m"
    GRAY="\033[90m"
fi

say_color() {
    color_code="$1"
    shift
    printf "%b%s%b\n" "$color_code" "$*" "$RESET"
}

TITLE_LINE="========================================================================"
SOFT_LINE="------------------------------------------------------------------------"

step() {
    printf '\n'
    say_color "$CYAN" "$1"
    say_color "$GRAY" "$SOFT_LINE"
}

info_line() {
    printf '  %-16s: %s\n' "$1" "$2"
}

note() {
    say_color "$DIM" "  $1"
}


progress_bar() {
    percent="$1"
    detail="${2:-}"
    complete="${3:-0}"

    if [ "$percent" -lt 0 ]; then percent=0; fi
    if [ "$percent" -gt 100 ]; then percent=100; fi

    cols=88
    if command -v tput >/dev/null 2>&1; then
        detected_cols=$(tput cols 2>/dev/null || echo 88)
        case "$detected_cols" in
            ''|*[!0-9]*) detected_cols=88 ;;
        esac
        cols=$(( detected_cols - 1 ))
    fi
    if [ "$cols" -lt 42 ]; then cols=42; fi
    if [ "$cols" -gt 96 ]; then cols=96; fi

    prefix="    "
    percent_text=$(printf '%3d%%' "$percent")
    min_bar_width=10
    max_bar_width=34
    reserved=$(( ${#prefix} + ${#percent_text} + 4 ))
    max_detail_len=$(( cols - reserved - min_bar_width - 2 ))
    if [ "$max_detail_len" -lt 0 ]; then max_detail_len=0; fi

    if [ "${#detail}" -gt "$max_detail_len" ]; then
        if [ "$max_detail_len" -gt 1 ]; then
            detail="${detail:0:$((max_detail_len - 1))}."
        else
            detail=""
        fi
    fi

    bar_width=$(( cols - reserved - ${#detail} ))
    if [ -n "$detail" ]; then bar_width=$((bar_width - 2)); fi
    if [ "$bar_width" -lt "$min_bar_width" ]; then bar_width=$min_bar_width; fi
    if [ "$bar_width" -gt "$max_bar_width" ]; then bar_width=$max_bar_width; fi

    filled=$(( (bar_width * percent + 50) / 100 ))
    empty=$(( bar_width - filled ))

    filled_part=""
    empty_part=""
    i=0
    while [ "$i" -lt "$filled" ]; do
        filled_part="${filled_part}="
        i=$((i + 1))
    done
    i=0
    while [ "$i" -lt "$empty" ]; do
        empty_part="${empty_part}-"
        i=$((i + 1))
    done

    printf '\r\033[2K%s' "$prefix"
    printf '%b%s%b' "$MAGENTA" "$filled_part" "$RESET"
    printf '%b%s%b' "$GRAY" "$empty_part" "$RESET"
    printf '  %b%s%b' "$GREEN" "$percent_text" "$RESET"
    if [ -n "$detail" ]; then
        printf '%b  %s%b' "$DIM" "$detail" "$RESET"
    fi

    if [ "$complete" = "1" ]; then
        printf '\n'
    fi
}

ok() {
    say_color "$GREEN" "[ OK ] $1"
}

warn() {
    say_color "$YELLOW" "[WARN] $1"
}

fail() {
    say_color "$RED" "[ERROR] $1"
}

init_log() {
    mkdir -p "$LOG_DIR"
    {
        echo "PHOTO-CAT macOS/Linux setup log"
        echo "Started: $(date '+%Y-%m-%dT%H:%M:%S')"
        echo "Version: $PROGRAM_VERSION"
        echo "Project folder: $PROJECT_DIR"
        echo "Operating system: $OS_NAME"
        echo
    } > "$SETUP_LOG"
}

append_log() {
    printf "%s\n" "$1" >> "$SETUP_LOG"
}

print_header() {
    say_color "$CYAN" "$TITLE_LINE"
    say_color "$BOLD$CYAN" "PHOTO-CAT - Setup"
    say_color "$CYAN" "$TITLE_LINE"
    echo
    info_line "Version" "$PROGRAM_VERSION"
    info_line "Project folder" "$PROJECT_DIR"
    info_line "Setup log" "$SETUP_LOG"
    echo
}

python_is_usable() {
    "$1" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

find_python() {
    PYTHON_CMD=""

    for candidate in python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if python_is_usable "$candidate"; then
                PYTHON_CMD="$candidate"
                return 0
            fi
        fi
    done

    return 1
}

sudo_cmd() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        fail "sudo was not found and administrator privileges are required."
        return 1
    fi
}

install_python_macos() {
    warn "Python 3.10+ was not found."

    if command -v brew >/dev/null 2>&1; then
        step "Step 1 of 3 - Install Python with Homebrew"
        note "This may take a few minutes. Homebrew output is shown because it may ask for system permissions."
        echo
        brew install python
        return $?
    fi

    echo
    fail "Homebrew was not found, so Python cannot be installed automatically on this Mac."
    echo
    echo "Manual fix:"
    echo "1. Download Python 3.10 or newer from python.org."
    echo "2. Install it."
    echo "3. Re-open Terminal in the PHOTO-CAT folder and run: sh START_UNIX.sh"
    echo

    if command -v open >/dev/null 2>&1; then
        open "https://www.python.org/downloads/macos/" >/dev/null 2>&1 || true
    fi

    return 1
}

install_python_linux() {
    warn "Python 3.10+ was not found."
    echo "PHOTO-CAT will try to install Python using your Linux package manager."
    note "Package manager output is shown because it may ask for administrator permissions."
    echo

    if command -v apt-get >/dev/null 2>&1; then
        sudo_cmd apt-get update || return 1
        sudo_cmd apt-get install -y python3 python3-venv python3-pip python3-tk || return 1
        return 0
    fi

    if command -v dnf >/dev/null 2>&1; then
        sudo_cmd dnf install -y python3 python3-pip python3-tkinter || return 1
        return 0
    fi

    if command -v yum >/dev/null 2>&1; then
        sudo_cmd yum install -y python3 python3-pip python3-tkinter || return 1
        return 0
    fi

    if command -v pacman >/dev/null 2>&1; then
        sudo_cmd pacman -Syu --needed python python-pip tk || return 1
        return 0
    fi

    if command -v zypper >/dev/null 2>&1; then
        sudo_cmd zypper install -y python3 python3-pip python3-tk || return 1
        return 0
    fi

    if command -v apk >/dev/null 2>&1; then
        sudo_cmd apk add python3 py3-pip py3-virtualenv tk || return 1
        return 0
    fi

    fail "Could not detect a supported Linux package manager."
    echo
    echo "Manual fix: install Python 3.10+, pip, venv and tkinter using your distribution package manager."
    echo
    return 1
}

python_has_tkinter() {
    "$1" - <<'PYTK' >/dev/null 2>&1
import tkinter
raise SystemExit(0)
PYTK
}

python_tk_formula_for() {
    "$1" - <<'PYTK' 2>/dev/null
import sys
print(f"python-tk@{sys.version_info.major}.{sys.version_info.minor}")
PYTK
}

install_tkinter_macos() {
    if ! command -v brew >/dev/null 2>&1; then
        fail "Tkinter is missing and Homebrew was not found."
        echo
        echo "Manual fix: install Python from python.org, then re-open Terminal and run: sh START_UNIX.sh"
        echo
        return 1
    fi

    venv_python="./.venv/bin/python"
    tk_formula="$(python_tk_formula_for "$venv_python")"
    if [ -z "$tk_formula" ]; then
        tk_formula="python-tk"
    fi

    warn "Tkinter is missing from this Python installation."
    note "PHOTO-CAT will install the matching Homebrew Tk package: $tk_formula"
    echo

    brew install "$tk_formula" || return 1
    return 0
}

install_tkinter_linux() {
    warn "Tkinter is missing from this Python installation."
    echo "PHOTO-CAT will try to install the Tkinter package using your Linux package manager."
    note "Package manager output is shown because it may ask for administrator permissions."
    echo

    if command -v apt-get >/dev/null 2>&1; then
        sudo_cmd apt-get update || return 1
        sudo_cmd apt-get install -y python3-tk || return 1
        return 0
    fi

    if command -v dnf >/dev/null 2>&1; then
        sudo_cmd dnf install -y python3-tkinter || return 1
        return 0
    fi

    if command -v yum >/dev/null 2>&1; then
        sudo_cmd yum install -y python3-tkinter || return 1
        return 0
    fi

    if command -v pacman >/dev/null 2>&1; then
        sudo_cmd pacman -Syu --needed tk || return 1
        return 0
    fi

    if command -v zypper >/dev/null 2>&1; then
        sudo_cmd zypper install -y python3-tk || return 1
        return 0
    fi

    if command -v apk >/dev/null 2>&1; then
        sudo_cmd apk add tk || return 1
        return 0
    fi

    fail "Could not detect a supported Linux package manager."
    echo
    echo "Manual fix: install the Tkinter package for your Python version, then run: sh START_UNIX.sh"
    echo
    return 1
}

ensure_gui_toolkit() {
    venv_python="./.venv/bin/python"

    progress_bar 0 "[checking GUI toolkit]"

    if python_has_tkinter "$venv_python"; then
        progress_bar 100 "[GUI toolkit ready]" 1
        ok "GUI toolkit is ready."
        return 0
    fi

    progress_bar 100 "[GUI toolkit missing]" 1

    case "$OS_NAME" in
        Darwin)
            install_tkinter_macos || return 1
            ;;
        Linux)
            install_tkinter_linux || return 1
            ;;
        *)
            fail "Tkinter is missing and this operating system is not supported by the automatic fixer."
            return 1
            ;;
    esac

    if python_has_tkinter "$venv_python"; then
        ok "GUI toolkit is ready."
        return 0
    fi

    fail "Tkinter is still missing after the automatic fix."
    echo
    echo "Manual fix for macOS Homebrew Python: brew install $(python_tk_formula_for "$venv_python")"
    echo "Then run: sh START_UNIX.sh"
    echo
    return 1
}

ensure_python() {
    step "Step 1 of 3 - Verify Python"
    progress_bar 0 "[Checking Python]"

    if find_python; then
        ok "Python found: $PYTHON_CMD"
        progress_bar 100 "[Python ready]" 1
        return 0
    fi

    case "$OS_NAME" in
        Darwin)
            install_python_macos || return 1
            ;;
        Linux)
            install_python_linux || return 1
            ;;
        *)
            fail "Unsupported operating system: $OS_NAME"
            echo "Use START_WINDOWS.bat on Windows, or START_UNIX.sh on macOS/Linux."
            return 1
            ;;
    esac

    if find_python; then
        ok "Python installed successfully: $PYTHON_CMD"
        progress_bar 100 "[Python ready]" 1
        return 0
    fi

    fail "Python still was not found, or the installed version is older than 3.10."
    return 1
}

ensure_libraries() {
    step "Step 2 of 3 - Prepare PHOTO-CAT dependencies"
    "$PYTHON_CMD" "src/install.py"
}

configure_tool() {
    step "Step 3 of 3 - Open graphical configurator"
    ensure_gui_toolkit || return 1
    note "Opening the graphical configurator..."
    "./.venv/bin/python" "src/configure_gui.py"
}

run_tool() {
    step "Step 3 of 3 - Run PHOTO-CAT pipeline"
    note "Running the PHOTO-CAT pipeline..."
    "./.venv/bin/python" "src/config_and_run.py"
}

finish_install() {
    echo
    say_color "$GREEN" "$TITLE_LINE"
    say_color "$BOLD$GREEN" "PHOTO-CAT setup is complete."
    say_color "$GREEN" "Run sh START_UNIX.sh again to configure and run."
    say_color "$GREEN" "$TITLE_LINE"
    echo
}

finish_configure() {
    echo
    say_color "$GREEN" "$TITLE_LINE"
    say_color "$BOLD$GREEN" "Configuration completed."
    say_color "$GREEN" "$TITLE_LINE"
    echo
}

finish_done() {
    echo
    say_color "$GREEN" "$TITLE_LINE"
    say_color "$BOLD$GREEN" "PHOTO-CAT finished successfully."
    say_color "$GREEN" "Check the configured output folder for results."
    say_color "$GREEN" "$TITLE_LINE"
    echo
}

error_message() {
    echo
    say_color "$RED" "$TITLE_LINE"
    fail "Something failed."
    info_line "Detailed setup log" "$SETUP_LOG"
    say_color "$RED" "$TITLE_LINE"
    echo
}

init_log
print_header

if ! ensure_python; then
    error_message
    exit 1
fi

if ! ensure_libraries; then
    error_message
    exit 1
fi

if [ "$MODE" = "INSTALL" ]; then
    finish_install
    exit 0
fi

if [ "$MODE" = "RUN" ]; then
    if ! run_tool; then
        error_message
        exit 1
    fi
    finish_done
    exit 0
fi

if ! configure_tool; then
    error_message
    exit 1
fi

finish_configure
exit 0
