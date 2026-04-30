#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

bash "scripts/start_linux_macos.sh" "$@"
status=$?

echo
read -r -p "Press Enter to close this window..."
exit "$status"
