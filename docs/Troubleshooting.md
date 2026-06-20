# Troubleshooting

## The GUI does not open

The graphical configurator requires Tkinter.

PHOTO-CAT checks for Tkinter before opening the GUI and attempts to handle common macOS/Linux cases. If the check fails, install Tkinter for the Python version being used or allow PHOTO-CAT to use its local runtime fallback.

## `.venv` is broken after moving the folder

PHOTO-CAT detects moved, stale, or partially deleted virtual environments before reuse. It rebuilds `.venv/` automatically when its stored project location no longer matches, its embedded path still points to an old location, or its Python executable is missing or cannot start.

Run:

```bash
photo-cat doctor
```

A recoverable stale environment is reported as `[WARN]`. For automation, use `photo-cat doctor --format json` and inspect the `project_venv` check. Close PHOTO-CAT, then run the Windows or Unix starter again. If recovery cannot remove the old folder, delete `.venv/` manually and start PHOTO-CAT again.

## A Homebrew Python path no longer exists

Homebrew may remove older Python framework paths during updates.

PHOTO-CAT checks whether `.venv/bin/python` can start. If it cannot, the environment is rebuilt before dependency installation continues.

## Dependencies fail to install

Check the console message and `logs/install.log`.

Common causes include:

- no internet connection during first setup
- blocked network access
- unsupported Python version
- incomplete Python installation
- permission issues in the project folder

## Column name errors

Column names are case-sensitive.

Open the catalogue or targets CSV and confirm that the configured column names match the headers exactly.

## Index folder errors

The query stage requires a complete index folder from the build stage.

Run the build stage again if files are missing, the catalogue changed, or the index folder was moved.

## Output path problems

Make sure the configured output directory is writable and not inside a protected system folder.

## `photo-cat doctor` reports missing project files after PyPI install

When PHOTO-CAT is installed from PyPI, `photo-cat doctor` runs in package-install mode. In this mode, project files such as `config.yaml`, `VERSION`, `.venv/`, and `.runtime/` are not required next to the installed package.

To validate a specific run configuration, pass it explicitly:

```bash
photo-cat doctor --config config.yaml
```

When `photo-cat doctor` is run from an extracted release/source folder, it also checks project context files such as `config.yaml` and `VERSION`.
