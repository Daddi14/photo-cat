# Configuration

PHOTO-CAT stores its runtime configuration in the root `config.yaml` file.

The recommended way to edit this file is through the graphical configurator opened by `START_WINDOWS.bat` or `START_UNIX.sh`.

## Main sections

The configuration controls:

- catalogue input path
- target input path or manual targets
- catalogue column mapping
- output directory
- neighbour index paths
- build stage options
- query stage options
- execution mode

## Catalogue path handling

When a catalogue CSV is selected in the GUI, PHOTO-CAT can initialize related paths such as the targets file, output/index folder, and query index folder.

The values remain editable before running.

## Build stage

The build stage creates a neighbour index from the catalogue.

Use this when the catalogue, coordinate columns, search radius, or output/index directory has changed.

Optional multi-band magnitude columns can be stored in the index for later
screening comparisons:

```yaml
build_neighbors_index:
  io:
    magnitude_columns:
      gaia_g: phot_g_mean_mag
      gaia_bp: phot_bp_mean_mag
      gaia_rp: phot_rp_mean_mag
```

`gaia_g` defaults to the configured `phot_g_mean_mag` column. Additional bands
are written as numeric arrays and recorded in `index_manifest.json`.

## Query stage

The query stage reads an existing index and processes selected targets.

Use this when the index already exists and you only need to query targets or adjust query options.

The default contamination model is `top_hat`, which preserves the historical
catalogue/aperture estimate. Optional radial weighting can be selected for
screening experiments:

```yaml
query_contamination_from_index:
  settings:
    contamination_bands: [gaia_g, gaia_bp, gaia_rp]
    contamination_model:
      mode: gaussian_psf
      gaussian_fwhm_arcsec: 47.0
```

For a tabulated radial aperture curve, use:

```yaml
query_contamination_from_index:
  settings:
    contamination_model:
      mode: radial_weight
      radial_weight_file: data/radial_weights.csv
```

The radial weight CSV must contain `sep_arcsec` and `weight` columns. These
models are still catalogue-level screening approximations unless the weights
come from an instrument-specific PSF/aperture calibration.

## Save + run

`Save + run` writes the current GUI settings to `config.yaml`, then starts the pipeline in a separate console.

The pipeline console shows progress and the final output path.


## Validation before processing

Before PHOTO-CAT starts an expensive build or query, it validates the configuration structure and the main setting types. Search radii and fields of view must be positive, chunk and buffer sizes must be positive integers, and boolean settings must be true or false.

File paths and CSV headers are then checked by the relevant build or query stage so the error message can identify the affected input.

## CLI overrides

Every value in `config.yaml` can also be overridden from the command line for a single run.

Example:

```bash
photo-cat run --config config.yaml --field-of-view-arcsec 60 --delta-mag 4
```

The YAML file is not permanently modified. CLI overrides are derived for one command, while the original loaded configuration remains unchanged. Configuration parsing and validation do not create output folders; build and query runtime resources are created only after validation succeeds. For all available override flags and examples, see [Command-line usage](Command-line.md).
