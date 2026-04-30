@echo off
setlocal EnableExtensions
cd /d "%~dp0"

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
