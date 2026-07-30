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
catalogue/aperture estimate. A 2D circular Gaussian PSF can be selected instead,
weighting each source by its radial flux decay:

```yaml
query_contamination_from_index:
  settings:
    field_of_view_arcsec: 47.0       # extraction/screening aperture
    contamination_bands: [gaia_g, gaia_bp, gaia_rp]
    contamination_model:
      mode: gaussian_psf
      gaussian_fwhm_arcsec: 2.0      # PSF full width at half maximum
      influence_sigma: 5.0           # how many sigmas of leakage still count
```

Under `gaussian_psf` each source contributes `exp(-r^2 / 2*sigma^2)` of its flux
at angular distance `r` from the aperture centre, with
`sigma = gaussian_fwhm_arcsec / 2.3548`.

The outer influence radius is **not configured directly**. It is derived as
`sigma * influence_sigma`, so the search radius follows the optics rather than an
unrelated hand-set number. With the values above, `sigma = 0.849"` and the
influence radius is `4.25"`. It may legitimately fall below the aperture radius:
a narrow PSF stops contributing leakage well inside a wide extraction circle. If
it exceeds the index build radius, PHOTO-CAT recomputes neighbours directly from
the catalogue for the queried targets, which is slower per target.

`top_hat` has no PSF scale, so it searches the aperture radius only.

Alongside the weights, `gaussian_psf` also reports aperture-integrated metrics
(`effective_target_flux`, `effective_contaminating_flux`, `contamination_ratio`,
`target_purity`), which integrate the circular Gaussian over the offset aperture.

This remains a catalogue-level screening approximation unless the FWHM comes from
an instrument-specific PSF calibration.

### Photometric band conversion

Contamination is estimated in the catalogue band by default. An optional
conversion estimates it in a mission band instead:

```yaml
query_contamination_from_index:
  settings:
    photometric_conversion:
      output_band: tess          # a built-in filter, or "custom"
      conversion_method: blackbody
      filter_file:               # required only when output_band is custom
      catalog: gaia_dr3
```

The selected output band is the reference band for the delta-magnitude cut,
contaminant list, primary flux fractions, counts, and PSF metrics. If that exact
band is already stored in the index (for example `gaia_bp` or `gaia_rp`), its
nominal catalogue magnitudes are used directly and no conversion is performed.

Otherwise, the colour (BP-RP) gives a blackbody-equivalent temperature; each
source's flux is integrated through the chosen filter, so
`m_out = m_anchor - 2.5*log10(R)` where
`R = F_out(Teff)/F_anchor(Teff)`. Because contamination uses only flux ratios
within one band, the output zero-point cancels and the anchor band's zero-point
is kept. This requires the catalogue colour bands (BP, RP) to be stored with
`magnitude_columns` during the index build. PHOTO-CAT loads those required bands
automatically; they do not have to be repeated in `contamination_bands`.

`output_band` is a built-in filter band key (`gaia_g`, `gaia_bp`, `gaia_rp`,
`tess`, `cheops`, `mauve`, and the Ariel channels `ariel_fgs1`, `ariel_fgs2`,
`ariel_visphot`, `ariel_airs_ch0`, `ariel_airs_ch1`, `ariel_nirspec`) or `custom`
with a `filter_file`. `conversion_method` is `blackbody` (default); `phoenix` and
`empirical` are selectable but require external data (a model-spectrum grid, or a
published relation) and error clearly until it is supplied.

Built-in filters live under `photo_cat/filters/<Mission>/<band>.dat`; adding a
mission is just dropping its official transmission curve there. Gaia, TESS,
CHEOPS, MAUVE and the Ariel channels ship as official curves. More filters can be
pulled from the SVO Filter Profile Service directly in the GUI (the "Download a
filter from SVO" panel picks a facility, lists its filters, and downloads one into
the library) or with `photo_cat.photometry.svo.download_filter`.

This is an approximate, catalogue-level screening estimate: real stars are not
blackbodies, and the reported effective temperature is a blackbody-equivalent
colour temperature, not a physical Teff. The output filter and its SHA-256
checksum are copied into query metadata.

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
