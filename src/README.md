# Source layout

PHOTO-CAT uses a standard Python `src/` package layout.

- `photo_cat/` contains the importable application package.
- Package/module names use lowercase `snake_case`.
- Classes use `PascalCase`.
- `cli.py` provides the unified `photo-cat` command-line interface.
- Developer entry points are defined in `pyproject.toml`.
- End-user launchers remain in the project root.

End users should still start PHOTO-CAT from `START_WINDOWS.bat` or `START_UNIX.sh`.
