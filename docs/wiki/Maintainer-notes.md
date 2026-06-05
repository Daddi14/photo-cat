# Maintainer notes

This page summarizes the release workflow for maintainers.

## Before a release

1. Update `VERSION`.
2. Test the starter files from a clean folder.
3. Run the example catalogue and targets.
4. Confirm `.venv/`, `.runtime/`, logs, and outputs are not committed.
5. Prepare release notes.
6. Create a clean ZIP archive.

## Release title

Use:

`PHOTO-CAT vX.Y.Z`

## Recommended release asset

Use a named archive such as:

`photo-cat-vX.Y.Z.zip`

## Generated files to exclude

- `.venv/`
- `.runtime/`
- `logs/`
- `output/`
- `data/output/`
- `__pycache__/`
- `*.pyc`
