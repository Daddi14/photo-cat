# PHOTO-CAT - Photometric Contamination Analyzer Tool

PHOTO-CAT is a beginner-friendly Python tool for building a neighbor index from a photometric catalog CSV and querying possible photometric contamination for target sources.

The project is designed so a non-technical user can download the release ZIP, extract it, and start from one launcher file.

## Quick start

Download the latest release ZIP, extract it, then run the starter for your operating system:

```text
Windows: double-click START_WINDOWS.bat
macOS:   double-click START_MACOS.command
Linux:   run ./START_LINUX.sh
```

The starter handles the beginner flow:

```text
check/install Python where possible -> create .venv -> install libraries -> open GUI -> run pipeline
```

Normal users should not need to open `src/` or `scripts/`.

## What the GUI does automatically

When you choose `Catalog CSV`, the GUI automatically fills:

```text
Targets CSV         = same file as Catalog CSV
Output/index folder = output folder next to the Catalog CSV
Query index folder  = same as Output/index folder
```

Example:

```text
Catalog CSV:         C:/Users/Name/Downloads/catalog.csv
Targets CSV:         C:/Users/Name/Downloads/catalog.csv
Output/index folder: C:/Users/Name/Downloads/output
Query index folder:  C:/Users/Name/Downloads/output
```

Then click `Save + run`.

## Required input columns

### Catalog CSV

Default Gaia-like catalog column names are:

```text
source_id, ra, dec, phot_g_mean_mag
```

The GUI lets you change these under `Catalog column names`.

Column names are **case-sensitive**. For example:

```text
ra is different from RA
Dec is different from dec
phot_g_mean_mag is different from PHOT_G_MEAN_MAG
```

Change the default column names only if your CSV header uses different names. The values in the GUI must match the CSV header exactly.

### Targets CSV

Default targets column name:

```text
source_id
```

If your targets CSV uses another header, change `Targets Source ID column` in the GUI.

### Manual target list

You can leave `Targets CSV` empty and provide source IDs manually in the GUI. This saves the config like this:

```yaml
TARGETS_INPUT: null
targets:
  - 123456789012345678
  - 987654321098765432
```

Manual targets ignore the `Targets Source ID column` field.

## Included example data

The release includes tiny example files in `data/`, so the tool can be tested immediately after installation.

```text
data/example_catalog.csv
data/example_targets.csv
```

## Python installation behavior

### Windows

`START_WINDOWS.bat` tries to install Python automatically if it is missing. It tries `winget` first, then the official Python installer from `python.org`. The installer is launched with PATH enabled for the current user.

If automatic installation fails, install Python 3.10 or newer manually from `python.org` and enable:

```text
Add python.exe to PATH
```

Then double-click `START_WINDOWS.bat` again.

### macOS

`START_MACOS.command` checks for Python 3.10 or newer.

If Python is missing and Homebrew is installed, it tries:

```bash
brew install python
```

If Homebrew is not installed, the script opens the official Python download page and tells the user what to install manually.

If macOS blocks the file because it was downloaded from the internet, right-click `START_MACOS.command`, choose `Open`, then confirm.

### Linux

`START_LINUX.sh` checks for Python 3.10 or newer.

If Python is missing, it tries the detected package manager:

```text
apt-get, dnf, yum, pacman, zypper, or apk
```

It also tries to install the packages needed for `venv`, `pip`, and the Tkinter GUI. Some Linux distributions may still require manual package installation depending on permissions and distribution version.

## Folder layout

```text
START_WINDOWS.bat      Main Windows launcher.
START_MACOS.command    Main macOS launcher.
START_LINUX.sh         Main Linux launcher.
START_HERE.txt         Very short instructions for non-technical users.
config.yaml            Configuration file used by the GUI and pipeline.
requirements.txt       Python libraries installed into .venv.
data/                  Tiny example CSV files.
src/                   Python source code. Normal users do not need to open it.
scripts/               Advanced/manual launchers used by the starters.
docs/                  Extra documentation, including Italian notes and publishing guide.
```

## Manual commands

Windows, after installation:

```bat
.venv\Scripts\python.exe src\config_and_run.py
```

Linux/macOS, after installation:

```bash
./.venv/bin/python src/config_and_run.py
```

## Troubleshooting

### The GUI says column names are missing

Open your CSV and check the header row. The configured column names must match exactly, including uppercase/lowercase.

Example: if your file has `RA`, type `RA` in the GUI, not `ra`.

### Python was not found

Run the starter for your operating system again.

For Windows, if automatic installation fails, install Python 3.10 or newer from `python.org` and enable `Add python.exe to PATH`.

For macOS, install Python 3.10 or newer from `python.org`, or install Homebrew and run:

```bash
brew install python
```

For Linux, install Python, pip, venv and Tkinter with your package manager. Examples:

```bash
sudo apt install python3 python3-venv python3-pip python3-tk
sudo dnf install python3 python3-pip python3-tkinter
sudo pacman -S python python-pip tk
```

### Libraries fail to install

Check that internet access is available, then run the starter again. The launcher reuses the existing `.venv` if it was already created.

### The tool cannot find a CSV

Open the GUI again and use the `Browse...` buttons. This avoids path typing mistakes.

## Maintainer notes

For GitHub/release instructions, see:

```text
docs/PUBLISHING.md
```

The recommended release asset name is:

```text
photo-cat-v1.0.0.zip
```

The user-facing release instruction should be:

```text
Extract the ZIP and run the starter for your operating system.
```


## Beginner-safe validation

PHOTO-CAT validates the selected files before running. If something is wrong, it shows a readable message instead of a Python traceback.

Common checks include:

- the Catalog CSV file exists;
- configured catalog columns exist exactly as written;
- column names are case-sensitive (`ra` is different from `RA`);
- RA, Dec and magnitude columns contain numeric values;
- the Targets CSV exists, unless manual targets are used;
- the Targets Source ID column exists exactly as written;
- the query index folder contains a complete built index when the build step is disabled.

If the tool reports missing columns, open the CSV header row and copy the column names exactly into the GUI.
