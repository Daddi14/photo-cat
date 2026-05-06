# PHOTO-CAT - Photometric Contamination Analyzer Tool

PHOTO-CAT is a Python tool for evaluating photometric contamination in astronomical catalogues. It builds a neighbour index from a photometric catalogue and queries potential contaminating sources around selected targets.

The project is designed for local, reproducible catalogue-level analysis with a graphical configuration interface, automatic virtual environment setup, and platform-specific launchers for Windows, macOS, and Linux.

## Features

- Build a neighbour index from a photometric catalogue.
- Query contamination around target sources.
- Configure runs through a graphical interface.
- Use either a targets CSV or a manual list of source IDs.
- Validate input files, column names, output folders, and index paths before execution.
- Automatically create and manage a local Python virtual environment.
- Detect moved project folders and rebuild the virtual environment when required.
- Provide readable error messages for common user-side configuration problems.

## Requirements

PHOTO-CAT requires:

- Python 3.10 or newer
- Internet access during the first dependency installation
- A photometric catalogue in CSV format

The launcher creates a local `.venv` folder and installs all required Python dependencies there. The virtual environment is local to the project folder and is not intended to be moved between paths.

## Installation and launch

Download the latest release ZIP, extract it, then run the launcher for your operating system.

```text
Windows       START_WINDOWS.bat
macOS/Linux   sh START_UNIX.sh
```

The launcher checks the Python installation, prepares the local virtual environment, installs or checks dependencies, and opens the graphical configurator.

Normal users should not need to open the `src/` or `scripts/` folders.

## Input data

PHOTO-CAT expects CSV input files.

The default catalogue schema follows common Gaia-style column names:

```text
source_id
ra
dec
phot_g_mean_mag
```

The default target identifier column is:

```text
source_id
```

Column names are case-sensitive and must match the CSV header exactly. If the input files use different column names, they can be changed in the graphical configurator.

## Configuration

The main configuration file is:

```text
config.yaml
```

The recommended way to edit it is through the graphical interface.

When a catalogue CSV is selected, PHOTO-CAT automatically initializes the related paths:

```text
Targets CSV
Output/index folder
Query index folder
```

These values remain editable before execution.

A manual list of target `source_id` values can also be used instead of a targets CSV.

## Output

PHOTO-CAT writes the generated neighbour index and query results to the configured output directory.

The query stage produces a JSON results file containing, for each processed target, the contamination metrics and the list of qualifying neighbouring sources.

## Project structure

```text
START_WINDOWS.bat      Windows launcher
START_UNIX.sh          macOS/Linux launcher
START_HERE.txt         Minimal launch notes
config.yaml            Runtime configuration
requirements.txt       Python dependencies
data/                  Small reference input files
src/                   Source code
scripts/               Launcher and platform support scripts
docs/                  Additional documentation
```

## Platform notes

### Windows

`START_WINDOWS.bat` attempts to detect Python automatically. If Python is missing, the launcher tries to install it using `winget` first, then the official Python installer.

If automatic installation fails, install Python 3.10 or newer manually and enable:

```text
Add python.exe to PATH
```

Then run `START_WINDOWS.bat` again.

### macOS and Linux

Use the shared Unix launcher:

```bash
sh START_UNIX.sh
```

On macOS, downloaded command files may be blocked by Gatekeeper. Running the Unix launcher through Terminal avoids that issue.

On Linux, the launcher attempts to use the detected package manager where possible, but some distributions may still require manual installation of Python, `pip`, `venv`, and Tkinter.

## Error handling

PHOTO-CAT validates common configuration problems before and during execution, including:

- missing input files;
- missing or mismatched CSV columns;
- case-sensitive column-name mismatches;
- invalid output folders;
- incomplete query index folders;
- non-numeric coordinate or magnitude fields;
- moved project folders with stale virtual environments.

When the project folder is moved after a virtual environment has already been created, PHOTO-CAT detects the stale `.venv`, removes it, and recreates it in the new location. User files such as `config.yaml`, `data/`, and output folders are not deleted.

## Documentation

Additional documentation is available in:

```text
docs/
```


## How to cite

Please include the following citation and acknowledgement in any published material that makes use of PHOTO-CAT.

### Citation

```text
<paper reference>
```

### Acknowledgement

```text
This research made use of Photo-cat, a Python package for photometric contamination analysis (<paper reference>), developed with the support of Blue Skies Space Ltd. (www.bssl.space).
```

Replace `<paper reference>` with the final paper reference once available.

## License

No license has been specified yet. Add a `LICENSE` file before distributing PHOTO-CAT publicly if reuse, modification, or redistribution terms should be defined.
