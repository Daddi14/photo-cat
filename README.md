<div align="center">

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/photo-cat-logo-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="assets/photo-cat-logo-light.png">
    <img src="assets/photo-cat-logo-colored.png" alt="Logo PHOTO-CAT" width="200">
  </picture>
</p>

[English](README.md) · [Italiano](README_IT.md)

**Photometric Contamination Analyzer Tool**

PHOTO-CAT builds a neighbour index from an astronomical catalogue and queries nearby sources that may contaminate selected photometric targets.

[Download and usage](docs/Download-and-usage.md) · [Command line](docs/Command-line.md) · [Input data](docs/Input-data.md) · [Troubleshooting](docs/Troubleshooting.md)

![Python](https://img.shields.io/badge/python-3.10--3.13-blue)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Runtime](https://img.shields.io/badge/runtime-project--local-green)
![Interface](https://img.shields.io/badge/interface-GUI%20%2B%20CLI-informational)

</div>

---

## Overview

PHOTO-CAT is a local Python tool for catalogue-level photometric contamination analysis.

It can build a neighbour index from a source catalogue, query selected targets, and write a JSON summary containing contamination metrics and neighbouring sources that match the configured field-of-view and magnitude limits.

PHOTO-CAT is designed for reproducible local use. It includes beginner-friendly launchers, a graphical configuration window, automatic dependency setup, and project-local runtime handling so user/system Python installations are not modified.

## Download and get started

1. Download the latest release archive.
2. Extract the archive.
3. Run the starter for your operating system:
   - Windows: double-click `START_WINDOWS.bat`
   - macOS/Linux: open Terminal in the folder and run `sh START_UNIX.sh`
4. Select your catalogue CSV in the graphical configurator.
5. Check the detected column names.
6. Click `Save + run`.

See [Download and usage](docs/Download-and-usage.md) for a fuller walkthrough.

## Features

- Build a neighbour index from a photometric catalogue.
- Query potential contaminating sources around selected targets.
- Configure runs through a graphical interface.
- Run the same workflow from a command-line interface for automation and remote systems, with direct overrides for every config value.
- Use either a targets CSV or a manual list of source IDs.
- Validate input files, column names, output folders, and index paths.
- Keep dependencies isolated inside the project `.venv` folder.
- Use a project-local runtime fallback when no suitable Python is available.
- Detect stale or moved virtual environments and rebuild them safely.
- Produce readable console output and user-facing error messages.

## Files

This distribution includes the following main files and folders:

- `README.md`, the file you are currently reading.
- `README_IT.md`, the Italian README.
- `START_WINDOWS.bat`, the main Windows launcher.
- `START_UNIX.sh`, the main macOS/Linux launcher.
- `config.yaml`, the runtime configuration file managed by the GUI.
- `data/`, example CSV files for quick testing.
- `docs/`, user and maintainer documentation.
- `tests/`, automated tests for configuration loading and the sample pipeline.
- `.github/workflows/`, continuous integration and package publishing workflows.
- `scripts/`, platform launcher helpers.
- `src/`, the PHOTO-CAT Python source code.
- `LICENSE`, the full GPL-3.0 license text.
- `REUSE.toml`, SPDX/REUSE licensing metadata.
- `CITATION.cff`, machine-readable citation metadata.
- `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md`, and `SECURITY.md`, repository community and maintenance files.

Runtime folders such as `.venv/`, `.runtime/`, logs, and output files are generated locally and should not be committed.

## Input data

PHOTO-CAT expects CSV input files.

The default catalogue columns follow common Gaia-style names:

- `source_id`
- `ra`
- `dec`
- `phot_g_mean_mag`

Column names are case-sensitive and must match the CSV header exactly. If your files use different names, change them in the graphical configurator before running the pipeline.

See [Input data](docs/Input-data.md) for details.

## Output

PHOTO-CAT writes generated index files and query results to the configured output directory.

The query stage produces a JSON file containing one result entry per processed target. Each entry includes the target data, contamination metrics, and the list of qualifying neighbouring sources.

See [Pipeline and output](docs/Pipeline-and-output.md) for details.

## Runtime and Python handling

PHOTO-CAT uses Python locally and avoids modifying the user’s system Python installation.

The launchers use an existing Python only when it is supported and passes the required checks. Supported versions are Python 3.10 through 3.13.

If no suitable Python is available, PHOTO-CAT uses a private runtime under `.runtime/` and installs project dependencies only into `.venv/`.

PHOTO-CAT does not permanently modify `PATH`, upgrade user Python, uninstall user Python, or install packages into the user’s system Python.

See [Runtime and Python](docs/Runtime-and-Python.md) for details.

## Command-line usage

After installing the package, the unified CLI is available as `photo-cat`.

Common commands:

```bash
photo-cat configure
photo-cat run --config config.yaml
photo-cat run --config config.yaml --input-catalog data/catalog.csv --ra-column RAJ2000 --dec-column DEJ2000 --mag-column Gmag --field-of-view-arcsec 60 --delta-mag 4
photo-cat build-index --config config.yaml --input-catalog data/catalog.csv --out-dir output/index
photo-cat query --config config.yaml --index-dir output/index --targets-input data/targets.csv --field-of-view-arcsec 47 --delta-mag 5
photo-cat doctor
```

The root launchers remain the recommended entry point for non-technical local users. The CLI is intended for automation, remote machines, and reproducible workflows. It supports direct runtime overrides for every value in `config.yaml`; see [Command-line usage](docs/Command-line.md). The doctor command supports both package-install checks and project-folder checks.

## Documentation

User documentation:

- [Download and usage](docs/Download-and-usage.md)
- [Input data](docs/Input-data.md)
- [Configuration](docs/Configuration.md)
- [Pipeline and output](docs/Pipeline-and-output.md)
- [Runtime and Python](docs/Runtime-and-Python.md)
- [Troubleshooting](docs/Troubleshooting.md)

Maintainer documentation:

- [Publishing PHOTO-CAT](docs/PUBLISHING.md)
- [Architecture and testing boundaries](docs/Architecture.md)
- [Public contracts](docs/Public-Contracts.md)
- [Development workflow](docs/Development.md)
- [Contributing](CONTRIBUTING.md)

## Troubleshooting

For common startup, dependency, Tkinter, CSV, and virtual environment issues, see [Troubleshooting](docs/Troubleshooting.md).

## Citation

Please include the following citation and acknowledgement in any published material that makes use of PHOTO-CAT.

Citation:

`<paper reference>`

Acknowledgement:

`This research made use of PHOTO-CAT, a Python package for photometric contamination analysis (<paper reference>), developed with the support of Blue Skies Space Ltd. (www.bssl.space).`

Replace `<paper reference>` with the final paper reference once available.

## Acknowledgements

The authors gratefully acknowledge:

- E. Drago for key contributions to the software implementation, testing workflow and the technical refinement of PHOTO-CAT.

- J. Burgio for the design and creation of the PHOTO-CAT logo and visual identity.

## License

PHOTO-CAT is distributed under the GNU General Public License v3.0 only. See [`LICENSE`](LICENSE) for the full license text.
