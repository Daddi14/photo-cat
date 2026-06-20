<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Development workflow

This guide is for contributors working from a source checkout of PHOTO-CAT.

For normal desktop use, use the root launchers instead. The development workflow is intended for code changes, reviews, automated checks, and reproducible debugging.

## Supported Python versions

The package supports Python 3.10 through 3.13.

Create an isolated virtual environment inside the repository:

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows Command Prompt
.venv\Scripts\activate.bat

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install the package in editable mode and the development tools:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest pytest-cov build
```

## Everyday checks

Run the complete suite:

```bash
pytest
```

Run only tests that protect documented user-visible behaviour:

```bash
pytest -m regression
```

Run isolated helper and validation tests:

```bash
pytest -m unit
```

Run coverage locally:

```bash
pytest --cov=photo_cat --cov-report=term-missing
```

CI enforces strict test markers and a coverage baseline of 78%. The baseline is a regression guard, not a claim that all code paths have equal scientific importance. New work should add meaningful assertions rather than tests written solely to increase the percentage.

## Public contracts and test types

Read [Public contracts](Public-Contracts.md) before changing a command, configuration key, index layout, or query result field.

- Use `@pytest.mark.regression` for tests that protect documented CLI, pipeline, index, or output behaviour.
- Use `@pytest.mark.unit` for isolated helpers and validation boundaries that may be reorganised internally.
- Every marked test needs a concise docstring when its technical, scientific, numerical, or compatibility intent is not obvious from the name.
- Keep tests focused on observable behaviour. Do not bind regression tests to private helper structure that a refactor may deliberately replace.

Shared test data and temporary-config helpers belong in `tests/conftest.py`. Runtime path rules are covered by `tests/test_path_policy.py`; configuration and process-state isolation are covered by `tests/test_configuration_lifecycle.py` and `tests/test_runtime_boundaries.py`. Preserve the distinction between config-relative and CLI-working-directory-relative paths.

When changing configuration flow, verify that parsing does not create output folders, CLI overrides do not mutate the base config, and child pipeline stages receive configuration through an explicit copied environment rather than a parent-process mutation.

## Verifying a change before opening a pull request

From the repository root, run:

```bash
python -m py_compile src/photo_cat/*.py
pytest
pytest --cov=photo_cat --cov-report=term-missing
python -m build
photo-cat --version
photo-cat doctor
```

On macOS/Linux, also check launcher syntax:

```bash
bash -n START_UNIX.sh scripts/*.sh
```

For changes to CLI, configuration, build/index, or query behaviour:

1. Run the appropriate regression tests with `pytest -m regression`.
2. Run the bundled end-to-end sample workflow with `pytest tests/test_pipeline_sample.py`.
3. Update English and Italian user documentation where behaviour changed.
4. Verify that no generated files are staged:

```bash
git status --short
git diff --check
```

Do not commit `.venv/`, `.runtime/`, build artifacts, generated indexes, logs, outputs, `__pycache__/`, or `*.pyc` files.

## Pull-request expectations

Keep pull requests focused. Explain the public behaviour affected, tests added or updated, and any follow-up work that remains.

The pull-request template includes the repository checks. Use it as a review checklist rather than checking boxes by habit.

## Related documentation

- [Contributing](../CONTRIBUTING.md)
- [Architecture and testing boundaries](Architecture.md)
- [Public contracts](Public-Contracts.md)
- [Command-line usage](Command-line.md)
- [Publishing PHOTO-CAT](PUBLISHING.md)
