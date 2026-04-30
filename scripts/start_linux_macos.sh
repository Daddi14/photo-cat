#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

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

print_header() {
    echo "============================================================"
    echo "PHOTO-CAT - Linux/macOS easy start"
    echo "============================================================"
    echo
    echo "This launcher will:"
    echo "  1. Check/install Python if possible."
    echo "  2. Create the local .venv folder."
    echo "  3. Install the required libraries."
    echo "  4. Open the graphical configurator."
    echo "  5. Optionally run the pipeline."
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
        echo "ERROR: sudo was not found and administrator privileges are required."
        return 1
    fi
}

install_python_macos() {
    echo "Python 3.10+ was not found."
    echo

    if command -v brew >/dev/null 2>&1; then
        echo "Homebrew was found. Installing Python with Homebrew..."
        echo "This can take a few minutes."
        echo
        brew install python
        return $?
    fi

    echo "Homebrew was not found, so I cannot safely install Python automatically on this Mac."
    echo
    echo "Manual fix:"
    echo "1. Download Python 3.10 or newer from python.org."
    echo "2. Install it."
    echo "3. Re-open this folder and double-click START_MACOS.command again."
    echo

    if command -v open >/dev/null 2>&1; then
        open "https://www.python.org/downloads/macos/" >/dev/null 2>&1 || true
    fi

    return 1
}

install_python_linux() {
    echo "Python 3.10+ was not found."
    echo "I will try to install Python using your Linux package manager."
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

    echo "ERROR: I could not detect a supported Linux package manager."
    echo
    echo "Manual fix: install Python 3.10+, pip, venv and tkinter using your distribution package manager."
    echo "Examples:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip python3-tk"
    echo "  Fedora:        sudo dnf install python3 python3-pip python3-tkinter"
    echo "  Arch:          sudo pacman -S python python-pip tk"
    return 1
}

ensure_python() {
    if find_python; then
        echo "Python found: $PYTHON_CMD"
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
            echo "ERROR: unsupported operating system: $OS_NAME"
            echo "Use START_WINDOWS.bat on Windows, START_MACOS.command on macOS, or START_LINUX.sh on Linux."
            return 1
            ;;
    esac

    if find_python; then
        echo
        echo "Python installed successfully."
        echo "Python found: $PYTHON_CMD"
        return 0
    fi

    echo
    echo "ERROR: Python still was not found, or the installed version is older than 3.10."
    return 1
}

ensure_libraries() {
    echo
    echo "Checking/installing the local virtual environment and libraries..."
    echo
    "$PYTHON_CMD" "src/install.py"
}

configure_tool() {
    echo
    echo "Opening the graphical configurator..."
    echo
    "./.venv/bin/python" "src/configure_gui.py"
}

run_tool() {
    echo
    echo "Running the pipeline with the local virtual environment..."
    echo
    "./.venv/bin/python" "src/config_and_run.py"
}

finish_install() {
    echo
    echo "============================================================"
    echo "Installation completed successfully."
    echo "You can now run the starter again to configure and run."
    echo "============================================================"
    echo
}

finish_configure() {
    echo
    echo "============================================================"
    echo "Configuration completed."
    echo "You can run the starter again whenever you want."
    echo "============================================================"
    echo
}

finish_done() {
    echo
    echo "============================================================"
    echo "Finished successfully."
    echo "Check the output folder for results."
    echo "============================================================"
    echo
}

error_message() {
    echo
    echo "============================================================"
    echo "Something failed."
    echo "Copy the error text above when asking for help."
    echo "============================================================"
    echo
}

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

if [ "$MODE" = "CONFIGURE" ]; then
    finish_configure
    exit 0
fi

echo
printf "Run the tool now? [y/N]: "
read -r answer
case "$answer" in
    y|Y|yes|YES|Yes)
        if ! run_tool; then
            error_message
            exit 1
        fi
        finish_done
        ;;
    *)
        finish_configure
        ;;
esac
