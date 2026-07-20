# -*- mode: python ; coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
#
# PyInstaller spec for a one-folder Windows build of photo-cat (CLI + GUI).
# Build from the repository root:
#     .venv\Scripts\python.exe -m PyInstaller packaging\photo-cat.spec --noconfirm --clean
# The result is dist\photo-cat\photo-cat.exe, which behaves like the installed
# `photo-cat` command (including `photo-cat.exe configure` to open the GUI).

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

project_root = Path(SPECPATH).parent
src_dir = project_root / "src"
assets_dir = project_root / "assets"

datas = []
binaries = []
hiddenimports = []

# Bundle the app's own metadata so importlib.metadata.version("photo-cat") works.
datas += copy_metadata("photo-cat")

# Heavy scientific dependencies whose data files and submodules PyInstaller does
# not fully discover automatically. matplotlib/scipy/numpy/pandas have built-in
# hooks and do not need this.
for package_name in ("dask", "pyarrow"):
    package_datas, package_binaries, package_hidden = collect_all(package_name)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

# Ship the logo assets so the GUI header renders in the frozen build (the GUI
# reads them from the PyInstaller extraction directory when frozen).
for asset_path in sorted(assets_dir.glob("*.png")):
    datas.append((str(asset_path), "assets"))

analysis = Analysis(
    [str(project_root / "packaging" / "entry_photo_cat.py")],
    pathex=[str(src_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "mypy", "ruff", "PyInstaller"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="photo-cat",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="photo-cat",
)
