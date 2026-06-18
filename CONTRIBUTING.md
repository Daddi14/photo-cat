<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Contributing to PHOTO-CAT

Thank you for considering a contribution to PHOTO-CAT.

## Start here

Read these before making a non-trivial change:

- [Development workflow](docs/Development.md)
- [Architecture and testing boundaries](docs/Architecture.md)
- [Public contracts](docs/Public-Contracts.md)
- [Command-line usage](docs/Command-line.md)

The Italian development and public-contract guides are available in [docs/Development_IT.md](docs/Development_IT.md) and [docs/Public-Contracts_IT.md](docs/Public-Contracts_IT.md).

## Contribution principles

1. Start from the latest `main` branch.
2. Keep each pull request focused and easy to review.
3. Preserve documented public behaviour unless the pull request explicitly describes a compatibility change.
4. Add or update tests for changed behaviour.
5. Keep English and Italian user-facing documentation structurally aligned.
6. Do not commit generated files such as `.venv/`, `.runtime/`, logs, outputs, build artifacts, `__pycache__/`, or `*.pyc` files.

## Before opening a pull request

At minimum, run:

```bash
python -m py_compile src/photo_cat/*.py
pytest
pytest --cov=photo_cat --cov-report=term-missing
photo-cat doctor
```

Use `pytest -m regression` whenever a change can affect documented CLI, configuration, index, or output behaviour.

For user-facing changes, update the relevant English and Italian documentation under `docs/`. For substantial changes, follow the full checklist in [Development workflow](docs/Development.md).

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

- Mark public CLI, pipeline, and result-contract tests with `@pytest.mark.regression`.
- Mark isolated helper and validation tests with `@pytest.mark.unit`.
- Keep user-visible CLI and pipeline behaviour protected by regression tests.
- Add focused unit tests when extracting a pure helper from build or query code.
- Add a short docstring when a test depends on a scientific convention, numerical tolerance, or non-obvious compatibility behaviour.
- Run `pytest --cov=photo_cat --cov-report=term-missing` before a substantial change to understand which paths remain untested.
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
