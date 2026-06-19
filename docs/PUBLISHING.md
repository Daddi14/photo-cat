# Publishing PHOTO-CAT

This page is for maintainers preparing a GitHub release.

## Final local test

Before publishing a release, test from a clean extracted folder.

Windows:

`START_WINDOWS.bat`

macOS/Linux:

`sh START_UNIX.sh`

Confirm that:

1. setup starts cleanly
2. a supported Python or local runtime is selected
3. `.venv/` is created or reused safely
4. dependencies are checked or installed
5. the graphical configurator opens
6. `Save + run` starts the pipeline
7. example data completes successfully
8. output paths and summaries are readable

## Files that should not be committed

Do not commit generated runtime or output files:

- `.venv/`
- `.runtime/`
- `__pycache__/`
- `*.pyc`
- `logs/`
- `output/`
- `data/output/`
- `.env`
- private datasets
- credentials or tokens

## Files that should not be included in release ZIPs

Do not include repository or duplicate/generated folders in release archives:

- `.git/`
- `.venv/`
- `.runtime/`
- `logs/`
- `output/`
- `data/output/`
- `__pycache__/`
- `docs/wiki/`

The canonical documentation lives in `docs/`. GitHub Wiki pages, if used, belong to the separate GitHub Wiki repository.

## Repository description

Recommended description:

`Photometric Contamination Analyzer Tool with local runtime setup and beginner-friendly launchers.`

Recommended topics:

`python`, `astronomy`, `photometry`, `catalogue`, `csv`, `gui`, `contamination`, `gaia`

## Release checklist

1. Update `VERSION`.
2. Update `pyproject.toml` to the same version.
3. Confirm `LICENSE` contains the full GPL-3.0 license text.
4. Confirm `pyproject.toml` declares `GPL-3.0-only`.
5. Confirm SPDX headers and `REUSE.toml` are current.
6. Run the automated test suite with `pytest`.
7. Confirm the GitHub Actions CI workflow passes on supported Python versions.
8. Prepare GitHub release notes.
9. Test Windows launch flow.
10. Test macOS/Linux launch flow where possible.
11. Test example catalogue and targets.
12. Confirm generated folders, `.git/`, and `docs/wiki/` are excluded from the release archive.
13. Create a clean release archive.
14. Publish the GitHub release.
15. Publish to TestPyPI first, then PyPI after the package is verified.

## Release title format

Use:

`vX.Y.Z`

Example:

`v1.0.0`

## Release asset format

Recommended release asset name:

`photo-cat-vX.Y.Z.zip`

Example:

`photo-cat-v1.0.0.zip`

A named ZIP is easier for non-technical users than relying only on GitHub’s automatic source-code archives.


## Python package publishing

The repository includes a GitHub Actions workflow for building and publishing the Python package.

Recommended release flow:

1. Confirm CI is passing.
2. Build and publish to TestPyPI with the manual workflow.
3. Install from TestPyPI in a clean environment and smoke-test the CLI.
4. Publish the GitHub release.
5. Publish to PyPI through the release workflow or a manual PyPI dispatch.

The publishing workflow is designed for PyPI Trusted Publishing. Configure the `testpypi` and `pypi` environments in the GitHub repository before using it.

After a successful TestPyPI upload, the package index can take a short time to expose the new version. Wait for clean-install verification instead of uploading the same version again. The maintainer release tool polls TestPyPI availability before continuing to GitHub Release and PyPI.
