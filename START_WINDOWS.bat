@echo off
REM SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
REM SPDX-License-Identifier: GPL-3.0-only
setlocal EnableExtensions
cd /d "%~dp0"
chcp 65001 >nul
mode con: cols=112 lines=52
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\fix_console_window.ps1" -Columns 112 -Lines 52 >nul 2>nul

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_windows.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ============================================================
    echo Something failed.
    echo Copy the error text above when asking for help.
    echo ============================================================
    echo.
    pause
    exit /b %EXIT_CODE%
)

exit /b 0
