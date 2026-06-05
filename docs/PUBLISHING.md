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

## Repository description

Recommended description:

`Photometric Contamination Analyzer Tool with local runtime setup and beginner-friendly launchers.`

Recommended topics:

`python`, `astronomy`, `photometry`, `catalogue`, `csv`, `gui`, `contamination`, `gaia`

## Release checklist

1. Update `VERSION`.
2. Update release notes.
3. Test Windows launch flow.
4. Test macOS/Linux launch flow where possible.
5. Test example catalogue and targets.
6. Confirm `.runtime/`, `.venv/`, logs, and outputs are excluded.
7. Create a clean release archive.
8. Publish the GitHub release.

## Release title format

Use:

`PHOTO-CAT vX.Y.Z`

## Release asset format

Recommended release asset name:

`photo-cat-vX.Y.Z.zip`

A named ZIP is easier for non-technical users than relying only on GitHub’s automatic source-code archives.
