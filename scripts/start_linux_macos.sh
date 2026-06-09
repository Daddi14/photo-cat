#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
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
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

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
RUNTIME_DIR="$PROJECT_DIR/.runtime"
RUNTIME_TOOLS_DIR="$RUNTIME_DIR/tools"
RUNTIME_PYTHON_DIR="$RUNTIME_DIR/python"
RUNTIME_DOWNLOADS_DIR="$RUNTIME_DIR/downloads"
RUNTIME_UV_DIR="$RUNTIME_TOOLS_DIR/uv"
PREFERRED_RUNTIME_PYTHON="3.12"
LOCAL_UV_PATH=""

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
if not ((3, 10) <= sys.version_info[:2] <= (3, 13)):
    raise SystemExit(1)
import venv
import ensurepip
import tkinter
raise SystemExit(0)
PY
}

find_python() {
    PYTHON_CMD=""

    for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if python_is_usable "$candidate"; then
                PYTHON_CMD="$candidate"
                return 0
            fi
        fi
    done

    return 1
}

uv_target_name() {
    machine="$(uname -m 2>/dev/null || echo unknown)"

    case "$OS_NAME:$machine" in
        Darwin:arm64|Darwin:aarch64)
            printf "%s\n" "uv-aarch64-apple-darwin.tar.gz"
            return 0
            ;;
        Darwin:x86_64|Darwin:amd64)
            printf "%s\n" "uv-x86_64-apple-darwin.tar.gz"
            return 0
            ;;
        Linux:aarch64|Linux:arm64)
            printf "%s\n" "uv-aarch64-unknown-linux-gnu.tar.gz"
            return 0
            ;;
        Linux:x86_64|Linux:amd64)
            printf "%s\n" "uv-x86_64-unknown-linux-gnu.tar.gz"
            return 0
            ;;
    esac

    return 1
}

download_file() {
    url="$1"
    output="$2"

    if command -v curl >/dev/null 2>&1; then
        curl -L "$url" -o "$output"
        return $?
    fi

    if command -v wget >/dev/null 2>&1; then
        wget -O "$output" "$url"
        return $?
    fi

    return 1
}

get_local_uv() {
    uv_path="$RUNTIME_UV_DIR/uv"
    if [ -x "$uv_path" ]; then
        LOCAL_UV_PATH="$uv_path"
        return 0
    fi

    target="$(uv_target_name)" || {
        fail "This platform is not supported by PHOTO-CAT's local runtime bootstrap."
        return 1
    }

    step "Step 1 of 3 - Prepare local runtime manager"
    note "Downloading a private runtime helper into the project folder."
    note "This does not modify your system Python or your PATH."

    mkdir -p "$RUNTIME_DOWNLOADS_DIR" "$RUNTIME_UV_DIR"
    archive_path="$RUNTIME_DOWNLOADS_DIR/$target"
    extract_path="$RUNTIME_DOWNLOADS_DIR/uv-extract"
    download_url="https://github.com/astral-sh/uv/releases/latest/download/$target"

    rm -rf "$extract_path"
    mkdir -p "$extract_path"

    append_log "Downloading local uv runtime helper: $download_url"

    if ! download_file "$download_url" "$archive_path" >> "$SETUP_LOG" 2>&1; then
        fail "Could not download the local runtime helper."
        echo
        echo "Manual fix: install Python 3.10-3.13 with Tkinter, then run: sh START_UNIX.sh"
        echo
        return 1
    fi

    if ! tar -xzf "$archive_path" -C "$extract_path" >> "$SETUP_LOG" 2>&1; then
        fail "Could not extract the local runtime helper."
        return 1
    fi

    found_uv="$(find "$extract_path" -type f -name uv -print | head -n 1)"
    if [ -z "$found_uv" ]; then
        fail "Could not find uv after extracting the local runtime helper."
        return 1
    fi

    cp "$found_uv" "$uv_path"
    chmod +x "$uv_path"
    ok "Local runtime helper is ready."
    LOCAL_UV_PATH="$uv_path"
    return 0
}

find_local_runtime_python() {
    if [ ! -d "$RUNTIME_PYTHON_DIR" ]; then
        return 1
    fi

    while IFS= read -r candidate; do
        if [ -n "$candidate" ] && [ -x "$candidate" ] && python_is_usable "$candidate"; then
            PYTHON_CMD="$candidate"
            return 0
        fi
    done <<EOF
$(find "$RUNTIME_PYTHON_DIR" -type f \( -name python3 -o -name python \) -print 2>/dev/null | sort)
EOF

    return 1
}

install_local_python_runtime() {
    warn "No supported Python 3.10-3.13 with Tkinter was found."
    note "PHOTO-CAT will download a private Python runtime into .runtime."
    note "Your installed Python versions will not be modified."
    echo

    if find_local_runtime_python; then
        ok "Local Python runtime found: $PYTHON_CMD"
        return 0
    fi

    get_local_uv || return 1
    uv_path="$LOCAL_UV_PATH"

    step "Step 1 of 3 - Prepare local Python runtime"
    note "Installing private Python $PREFERRED_RUNTIME_PYTHON into the project folder."

    mkdir -p "$RUNTIME_PYTHON_DIR"

    append_log "Installing local Python runtime with uv."
    append_log "> $uv_path python install $PREFERRED_RUNTIME_PYTHON --install-dir $RUNTIME_PYTHON_DIR"

    if ! "$uv_path" python install "$PREFERRED_RUNTIME_PYTHON" --install-dir "$RUNTIME_PYTHON_DIR" >> "$SETUP_LOG" 2>&1; then
        fail "Could not install the private PHOTO-CAT Python runtime."
        echo "Detailed setup log: $SETUP_LOG"
        return 1
    fi

    if find_local_runtime_python; then
        ok "Local Python runtime is ready: $PYTHON_CMD"
        return 0
    fi

    fail "The private Python runtime was installed, but PHOTO-CAT could not find a usable Python inside .runtime."
    return 1
}


python_has_tkinter() {
    "$1" - <<'PYTK' >/dev/null 2>&1
import tkinter
raise SystemExit(0)
PYTK
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
    fail "Tkinter is missing from the Python used by PHOTO-CAT."
    echo
    echo "PHOTO-CAT no longer installs system packages automatically."
    echo "Delete .venv and .runtime, then run START_UNIX.sh again so PHOTO-CAT can create a private local runtime."
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

    progress_bar 100 "[local runtime needed]" 1
    install_local_python_runtime || return 1
}

ensure_libraries() {
    step "Step 2 of 3 - Prepare PHOTO-CAT dependencies"
    "$PYTHON_CMD" -m photo_cat.install
}

configure_tool() {
    step "Step 3 of 3 - Open graphical configurator"
    ensure_gui_toolkit || return 1
    note "Opening the graphical configurator..."
    "./.venv/bin/python" -m photo_cat.configure_gui
}

run_tool() {
    step "Step 3 of 3 - Run PHOTO-CAT pipeline"
    note "Running the PHOTO-CAT pipeline..."
    "./.venv/bin/python" -m photo_cat.config_and_run
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
