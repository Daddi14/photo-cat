# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Static security contracts for executable runtime-bootstrap downloads."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_windows_runtime_helper_is_version_pinned_and_hash_verified(project_root: Path) -> None:
    """The Windows starter must never execute a mutable or unverified uv release asset."""
    script = (project_root / "scripts" / "start_windows.ps1").read_text(encoding="utf-8")

    assert "releases/latest/download" not in script
    assert '$UvVersion = "0.11.16"' in script
    assert "Get-FileHash -Path $archivePath -Algorithm SHA256" in script
    assert "Downloaded uv archive failed SHA-256 verification." in script


@pytest.mark.unit
def test_unix_runtime_helper_is_version_pinned_and_hash_verified(project_root: Path) -> None:
    """The Unix starter must require TLS and verify each supported release archive."""
    script = (project_root / "scripts" / "start_linux_macos.sh").read_text(encoding="utf-8")

    assert "releases/latest/download" not in script
    assert 'UV_VERSION="0.11.16"' in script
    assert "curl --proto '=https' --proto-redir '=https' --tlsv1.2 --fail" in script
    assert 'actual_sha256="$(file_sha256 "$archive_path")"' in script
    assert "Downloaded uv archive failed SHA-256 verification." in script
