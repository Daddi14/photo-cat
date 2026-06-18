# Source layout

PHOTO-CAT uses a standard Python `src/` package layout.

- `photo_cat/` contains the importable application package.
- Package/module names use lowercase `snake_case`.
- Classes use `PascalCase`.
- `cli.py` provides the unified `photo-cat` command-line interface.
- `path_policy.py` owns non-GUI runtime path resolution, filesystem validation, and index/query path naming.
- `load_config.py` owns isolated configuration documents, typed parsing, and runtime-input validation boundaries.
- `cli_overrides.py` derives disposable override configs without changing the base mapping or parent process environment.
- Developer entry points are defined in `pyproject.toml`.
- End-user launchers remain in the project root.

End users should still start PHOTO-CAT from `START_WINDOWS.bat` or `START_UNIX.sh`.

## Contributor resources

- [Development workflow](../docs/Development.md)
- [Public contracts](../docs/Public-Contracts.md)
