@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."
chcp 65001 >nul
mode con: cols=128 lines=42
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0fix_console_window.ps1" -Columns 128 -Lines 42 >nul 2>nul
title PHOTO-CAT Pipeline

set "PHOTO_CAT_COMPACT_LOG=1"
set "PHOTO_CAT_FORCE_COLOR=1"

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo The local virtual environment was not found.
    echo.
    echo Run START_WINDOWS.bat first.
    echo.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" "src\config_and_run.py"
set "EXIT_CODE=%ERRORLEVEL%"

echo.
echo Press any key to close this window.
pause >nul
exit /b %EXIT_CODE%
