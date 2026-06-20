# Runtime and Python

PHOTO-CAT is designed to keep its runtime local to the project folder.

## Supported Python versions

PHOTO-CAT can use an existing Python installation only if it is supported and passes the required environment checks.

Supported versions:

- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13

Older versions are ignored. Python 3.14 and newer are not selected by default yet.

## Local runtime fallback

If no suitable Python is available, PHOTO-CAT uses a private runtime under:

`.runtime/`

This avoids modifying the user’s system Python installation.

## Virtual environment

Dependencies are installed only into:

`.venv/`

PHOTO-CAT does not install packages into the user’s global Python environment.

## What PHOTO-CAT does not do

PHOTO-CAT does not:

- permanently modify `PATH`
- upgrade user Python
- uninstall user Python
- install dependencies into system Python
- overwrite an existing work Python installation
- require users to run Poetry or uv manually

## Stale environment detection

If `.venv/` is moved, broken, partially deleted, or points to a removed Python runtime, PHOTO-CAT rebuilds it automatically.

`photo-cat doctor` reports a stale local environment as a recoverable warning. Automated checks can use `photo-cat doctor --format json` and inspect the `project_venv` diagnostic.

This helps with common cases such as moving the project folder or Homebrew removing an older Python framework path on macOS.
