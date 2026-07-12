# Configuration

PHOTO-CAT stores its runtime configuration in the root `config.yaml` file.

The recommended way to edit this file is through the graphical configurator opened by `START_WINDOWS.bat` or `START_UNIX.sh`.

## Main sections

The configuration controls:

- interface language (`en` or `it`)
- catalogue input path
- target input path or manual targets
- catalogue column mapping
- output directory
- neighbour index paths
- build stage options
- query stage options
- execution mode

## Interface language

The `interface.language` value selects the user-facing language:

```yaml
interface:
  language: en  # en or it
```

It applies to the GUI, tooltips, CLI help, console messages, warnings, and expected errors. The GUI language selector updates the interface immediately and saves the choice with the configuration. Scientific plot labels deliberately remain in English so exported figures are consistent across runs and suitable for international publication.

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
    field_of_view_arcsec: 47.0       # extraction/screening aperture
    influence_radius_arcsec: 75.0   # optional outer leakage search
    contamination_bands: [gaia_g, gaia_bp, gaia_rp]
    contamination_model:
      mode: gaussian_aperture
      gaussian_fwhm_arcsec: 47.0
```

`influence_radius_arcsec` defaults to `field_of_view_arcsec`, must be at least
as large as it, and cannot exceed the index build radius. `gaussian_aperture`
integrates a circular Gaussian PSF over the configured circular aperture and
normalizes the result to the centered target throughput. The older
`gaussian_psf` mode remains available as a simple point-response approximation.

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

### Empirical mission-band transformations

An optional versioned YAML profile can derive one named mission magnitude from
stored catalogue bands:

```yaml
query_contamination_from_index:
  settings:
    bandpass_transform_file: examples/reproducibility/bandpass_transform_example.yaml
```

The profile defines `output_band`, `base_band`, two `color_bands`, polynomial
`coefficients`, calibrated colour/magnitude limits, an `out_of_range` policy,
and a calibration reference. The convention is:

```text
m_output = m_base + c0 + c1*colour + c2*colour^2 + ...
colour = m_color_band_1 - m_color_band_2
```

The required input bands must have been stored with `magnitude_columns` during
the index build. `out_of_range: null` excludes uncalibrated values;
`out_of_range: extrapolate` retains them but marks each affected target as
`extrapolated`. The profile and its SHA-256 checksum are copied into query
metadata. This is an empirical colour transformation, not passband integration
over a spectral energy distribution.

## Save and run pipeline

`Save and run pipeline` writes the current GUI settings to `config.yaml`, then starts the pipeline in a separate console.

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
