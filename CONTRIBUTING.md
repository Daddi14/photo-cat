# Contributing to PHOTO-CAT

Thank you for considering a contribution to PHOTO-CAT.

## Before opening a pull request

1. Start from the latest `main` branch.
2. Keep changes focused and easy to review.
3. Do not commit generated files such as `.venv/`, `.runtime/`, `logs/`, `output/`, `data/output/`, `__pycache__/`, or `*.pyc`.
4. Preserve the existing source layout under `src/photo_cat/`.
5. Keep user-facing documentation in both English and Italian when applicable.

## Local checks

Before submitting a pull request, run at least:

```bash
python -m py_compile src/photo_cat/*.py
pytest
```

On macOS/Linux, also check shell launcher syntax:

```bash
bash -n START_UNIX.sh scripts/*.sh
```

If possible, test the full user flow from a clean extracted folder:

- Windows: `START_WINDOWS.bat`
- macOS/Linux: `sh START_UNIX.sh`

## Documentation changes

When changing user-facing behaviour, update the relevant files in `docs/`.

English and Italian documentation should stay structurally aligned. Do not keep duplicate documentation under `docs/wiki/`; GitHub Wiki content, if used, belongs to the separate wiki repository.

## Licensing

PHOTO-CAT is licensed under GPL-3.0-only.

New source and launcher files should include:

```text
SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
SPDX-License-Identifier: GPL-3.0-only
```

Files that cannot use visible headers should be covered by `REUSE.toml`.


## Test structure

Shared temporary input files and reusable config helpers live in `tests/conftest.py`.

- Keep user-visible CLI and pipeline behaviour protected by regression tests.
- Add focused unit tests when extracting a pure helper from build or query code.
- Add a short docstring when a test depends on a scientific convention, numerical tolerance, or non-obvious compatibility behaviour.
- Do not tie tests to private implementation details that are expected to change during refactoring.

## Command-line interface

The unified CLI entry point is `photo-cat`. Keep GUI, CLI, and direct module behaviour aligned when changing pipeline behaviour.

Useful development commands:

```bash
photo-cat run --config config.yaml
photo-cat build-index --config config.yaml
photo-cat query --config config.yaml
photo-cat doctor
```
