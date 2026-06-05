# Launcher scripts

This folder contains helper scripts used by the root launchers.

Normal users should run only the root starter files:

- `START_WINDOWS.bat`
- `START_UNIX.sh`

## Main helpers

- `start_windows.ps1`, main Windows launcher logic.
- `start_linux_macos.sh`, main macOS/Linux launcher logic.
- `run_pipeline_windows.bat`, opens the pipeline in a separate Windows console.
- `run_pipeline_unix.sh`, runs the pipeline from macOS/Linux after `Save + run`.
- `fix_console_window.ps1`, adjusts the Windows console size.

## Compatibility helpers

- `install_windows.bat`
- `configure_windows.bat`
- `run_windows.bat`
- `install_linux_macos.sh`
- `configure_linux_macos.sh`
- `run_linux_macos.sh`

These are provided for advanced/manual workflows. Most users do not need them.
