@echo off
REM SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
REM SPDX-License-Identifier: GPL-3.0-only
REM Build a one-folder Windows executable for PHOTO-CAT (CLI + GUI).
REM Produces dist\photo-cat\photo-cat.exe.
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo The local virtual environment was not found.
    echo Run START_WINDOWS.bat first so it can create the local virtual environment.
    echo.
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller
".venv\Scripts\python.exe" -m PyInstaller packaging\photo-cat.spec --noconfirm --clean
set "EXIT_CODE=%ERRORLEVEL%"

if %EXIT_CODE% EQU 0 (
    echo.
    echo Build complete: dist\photo-cat\photo-cat.exe
)
exit /b %EXIT_CODE%
