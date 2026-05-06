# Publishing PHOTO-CAT on GitHub

This guide is for the maintainer.

## 1. Final local test before publishing

Use a clean folder, extract the project, then test the beginner flow:

```text
Windows: double-click START_WINDOWS.bat
macOS/Linux: open Terminal in the photo-cat folder and run: sh START_UNIX.sh
```

Confirm that:

```text
1. .venv is created.
2. requirements are installed.
3. the GUI opens.
4. the example config can be saved.
5. Save + run starts the pipeline.
6. column-name errors are readable, not huge tracebacks.
```

## 2. Repository name

Recommended GitHub repository name:

```text
photo-cat
```

Recommended description:

```text
Photometric Contamination Analyzer Tool with beginner-friendly launchers for Windows, macOS and Linux.
```

Recommended topics:

```text
python, astronomy, photometry, csv, gui, contamination, gaia
```

## 3. Publish with GitHub Desktop

1. Open GitHub Desktop.
2. Add the local `photo-cat` folder as a repository.
3. Commit the files with a message like:

```text
Initial public release
```

4. Click `Publish repository`.
5. Set visibility to `Public`.
6. Publish.

## 4. Files that should not be committed

Before publishing, make sure these are not included:

```text
.venv/
__pycache__/
*.pyc
output/
data/output/
.env
private datasets
personal paths
credentials
tokens
```

The included `.gitignore` is set up for this.

## 5. Add a license

Add a license before promoting the project as open source.

Common simple choice:

```text
MIT License
```

More restrictive copyleft choice:

```text
GPLv3
```

On GitHub, create a file called `LICENSE`, use `Choose a license template`, select the license, and commit it.

## 6. Create a release

On GitHub:

```text
Repository page -> Releases -> Draft a new release
```

Use:

```text
Tag: vX.Y.Z
Title: PHOTO-CAT vX.Y.Z
```

Attach a manually created ZIP named:

```text
photo-cat-vX.Y.Z.zip
```

Do not rely only on GitHub's automatic "Source code (zip)" asset. A clearly named release ZIP is easier for non-technical users.

## 7. Suggested release notes

```markdown
# PHOTO-CAT vX.Y.Z

First public release.

## Quick start

1. Download `photo-cat-vX.Y.Z.zip` from this release.
2. Extract the ZIP.
3. Run the starter for your operating system:
   - Windows: double-click `START_WINDOWS.bat`
   - macOS/Linux: open Terminal in the folder and run `sh START_UNIX.sh`
4. Select your Catalog CSV in the GUI.
5. Check the column names.
6. Click `Save + run`.

## Included

- Windows launcher and shared macOS/Linux Unix launcher.
- Automatic local virtual environment setup.
- Automatic dependency installation.
- GUI configurator for `config.yaml`.
- Case-sensitive column-name validation with readable errors.
- Manual source_id target list support.
- Example CSV files.
- English and Italian documentation.
- How to cite section in README.md.
- macOS/Linux Save + run starts the pipeline in a separate terminal.
- Catalog CSV path changes auto-fill related paths even when typed manually.

## Requirements

Python 3.10 or newer.

The starter attempts to install/check Python automatically where possible.
```
