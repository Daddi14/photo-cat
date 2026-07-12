# PHOTO-CAT Windows executable (PyInstaller spike)

This folder packages PHOTO-CAT into a standalone Windows executable so users can
run it without installing Python. It is a **validated spike**: the build works
end to end today, with a few productionization decisions listed below.

## Build

```bat
packaging\build_windows.bat
```

This installs PyInstaller into the local `.venv` and runs
`packaging\photo-cat.spec`. The result is a one-folder distribution:

```
dist\photo-cat\photo-cat.exe
```

`photo-cat.exe` is the same CLI as the installed `photo-cat` command, so:

- `photo-cat.exe --version`, `photo-cat.exe doctor`, `photo-cat.exe summarize ...`
  and every other subcommand work directly.
- `photo-cat.exe configure` opens the graphical configurator.

## What was verified

Built with PyInstaller 6.21 on Windows 10, Python 3.13:

- **Builds cleanly** into a one-folder bundle of **~277 MB**.
- `photo-cat.exe doctor` reports **all checks passing** — tkinter, NumPy, pandas,
  SciPy, tqdm, PyYAML, **PyArrow**, and **Dask** are all bundled and importable.
- CLI commands run, including the matplotlib backend
  (`photo-cat.exe plot <result>.json --backend matplotlib`).
- The **GUI launches** from the executable and renders the logo (assets are
  bundled and read from the PyInstaller extraction directory).
- The GUI is **frozen-aware** (`sys.frozen`): it invokes tool/pipeline commands
  through the executable itself (`photo-cat.exe <subcommand>`) instead of
  `python -m photo_cat.cli`, and reads/writes `config.yaml` and outputs next to
  the executable.

## How it fits together

- `entry_photo_cat.py` — frozen entry point; dispatches to `photo_cat.cli.main`.
- `photo-cat.spec` — bundles the app metadata (`importlib.metadata` support),
  fully collects `dask` and `pyarrow` (matplotlib/scipy/numpy/pandas use
  PyInstaller's built-in hooks), and ships the logo assets.
- `src/photo_cat/configure_gui.py` — when frozen, resolves assets from
  `sys._MEIPASS`, anchors `config.yaml`/outputs next to the executable, and builds
  subcommand invocations against the executable itself.

## Productionization decisions (not done in this spike)

- **Config & data packaging.** A frozen app anchors `config.yaml` and output
  folders next to the executable. Ship a default `config.yaml` (and, optionally,
  the example data) alongside the executable, or add a first-run setup step. The
  build intentionally does **not** bundle `data/` or a default `config.yaml`.
- **Console window.** The spec uses `console=True` so CLI output is visible; the
  GUI therefore opens with a console window. For a pure double-click GUI, ship a
  second windowed executable (`console=False`) or a small launcher.
- **Size / distribution.** One-folder (~277 MB) is the recommended, reliable
  form; zip it for distribution. `--onefile` yields a single executable but with
  slower startup (it extracts on each run) and more antivirus friction.
- **Code signing.** Unsigned PyInstaller executables can trip SmartScreen and
  antivirus heuristics. Sign the executable for public distribution.
- **CI artifact.** Building the executable on a Windows runner and uploading it as
  a release artifact is a natural follow-up; it is intentionally not wired into CI
  here because the build is heavy and slow.
- **End-to-end pipeline from the frozen GUI.** The `photo-cat.exe run`
  self-invocation is wired, but a full build+query run from the frozen GUI should
  be validated with a real dataset and an adjacent `config.yaml` before release.

## Recommendation

A Windows one-folder build is **feasible and low-risk**. The remaining work is
packaging policy (config/data layout, optional windowed GUI, code signing), not
technical unknowns.
