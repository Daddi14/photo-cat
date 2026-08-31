# Pipeline and output

PHOTO-CAT has two main pipeline stages.

## Stage 1: Build neighbour index

The build stage reads the catalogue, validates the configured columns, converts coordinates, and builds an index of neighbouring sources.

Generated index files are written to the configured index/output directory. The
index includes `index_manifest.json`, which records the catalogue fingerprint,
build radius, source count, and completion state. Checkpoints and final files are
published atomically so interrupted builds can resume without appending
uncommitted records. The index format is safe by construction: it stores only
non-object NumPy arrays and never loads executable pickle payloads.

## Stage 2: Query contamination

The query stage loads the index and processes the selected targets.

For each target, PHOTO-CAT identifies neighbouring sources inside the configured
circular query radius (`field_of_view_arcsec`) and applies the configured
magnitude criteria. The query is rejected if this radius is larger than the
radius represented by the index. The extra-flux metric and contaminant list use
the same radius and magnitude selection.

## Contamination model and terminology

PHOTO-CAT reports catalogue-level, aperture-like contamination metrics.
It is best interpreted as a contamination risk-assessment or target-screening
tool unless mission-specific modelling is added downstream.

- `field_of_view_arcsec` is the circular angular radius used by the query to
  select neighbours around each target. Despite the historical config key name,
  it is not automatically a detector field of view, PSF width, extraction
  aperture, or pixel scale; use the value that matches the screening aperture
  you want to test.
- The outer neighbour-search radius is derived, not configured: under
  `gaussian_psf` it is `sigma * influence_sigma`, where
  `sigma = gaussian_fwhm_arcsec / 2.3548`. `top_hat` searches the aperture only.
- `delta_mag` is the maximum allowed catalogue magnitude difference,
  `mag_neighbour - mag_target`, for a neighbour to be selected.
- A `contaminant` in the JSON output means a neighbour that passes both the
  configured circular-radius cut and the `delta_mag` cut.
- `contamination_model` records the query weighting mode. `top_hat` is the
  historical unweighted circular-aperture estimate. `gaussian_psf` applies a
  2D circular Gaussian PSF from the configured FWHM, so each source's flux
  decays as `exp(-r^2 / 2*sigma^2)` with angular distance from the aperture
  centre, and additionally reports aperture-integrated flux metrics.
- `flux_fraction_selected` is computed from the same selected contaminants as
  `num_contaminants`, using catalogue magnitude ratios
  `10 ** (-0.4 * (mag_neighbour - mag_target))`, and is reported as a
  percentage of the target flux.
- `flux_fraction_all_neighbors` uses every valid neighbour inside the circular
  query radius, even if it does not pass `delta_mag`.
- `flux_fraction_extra` is an alias of `flux_fraction_selected`.

The optional Gaussian PSF weights remain a circular radial model, not full
instrument simulations. They can estimate leakage from sources between the
aperture and influence radii, but do not model asymmetric or spatially varying
PSFs, detector pixels, diffraction or scattered light. Optional band conversion
can use a blackbody, a published Gaia relation, or synthetic photometry of a
locally prepared PHOENIX/BT-Settl atmosphere grid. PHOTO-CAT selects/interpolates
existing model spectra; it does not fit or generate stellar atmospheres.

## Output JSON

The query stage writes a JSON result file to the configured output folder.

Each target result includes:

- target source ID
- target coordinates
- target `magnitude`, `magnitude_band`, and `magnitude_source`, identifying the
  nominal or converted band used for all primary metrics and selection cuts
- selected-contaminant flux fraction
- all-neighbour-in-radius flux fraction
- optional per-band selected/all-neighbour flux-fraction dictionaries
- optional converted mission-band metrics, effective temperature, and per-target
  conversion status when no exact catalogue output band is available
- for PHOENIX, atmospheric parameters and provenance, relative target flux,
  normalization factor, quality, extinction flag, and explicit fallback reason
- weighted inside-aperture, outside-aperture, and total flux fractions
- outside-aperture neighbour counts and selected-source records
- number of neighbours inside the circular radius
- number of selected contaminants
- contaminant source list
- contaminant coordinates, magnitudes, and separations

For reproducibility, each query also writes a sidecar metadata JSON file under
`INDEX_DIR/results/metadata/`. The sidecar records the PHOTO-CAT version, selected
configuration values, target count, index manifest, catalogue SHA-256 from the
index build, optional photometric-conversion filter checksum, and the model-scope notes
above. The target-result JSON remains a
plain list of target entries.

By default, target IDs that are invalid or absent from the index are skipped with
warnings. Set `include_missing_targets: true` or pass `--include-missing-targets`
to preserve those requested IDs as JSON rows with `status` set to
`missing_from_index` or `invalid_target_id` and science metrics set to `null`.

## Derived summaries, plots, reports, and benchmarks

After a query, result files can be converted into reproducible
products:

```bash
photo-cat summarize INDEX_DIR/results/result.json --format json --output summary.json
photo-cat export INDEX_DIR/results/result.json --format csv --output result.csv
photo-cat plot INDEX_DIR/results/result.json --kind contaminant-counts --output counts.svg
photo-cat plot INDEX_DIR/results/result.json --kind sky-map --backend matplotlib --output sky-map.png
photo-cat plot INDEX_DIR/results/result.json --kind separations-normalized --output separations_area_norm.svg
photo-cat plot INDEX_DIR/results/result.json --kind flux-vs-separation --output flux_vs_separation.svg
photo-cat plot INDEX_DIR/results/result.json --kind sky-map --output sky-map.svg
photo-cat publication-plots INDEX_DIR/results/result.json --aperture-arcsec 47 --output-dir publication_plots
photo-cat report INDEX_DIR/results/result.json --format html --output report.html
photo-cat report INDEX_DIR/results/result.json --format pdf --output report.pdf
photo-cat provenance data/catalog.csv --output catalog_provenance.json
photo-cat benchmark --config config.yaml --output benchmark.json
photo-cat benchmark-table benchmark.json --output benchmark_table.md
photo-cat reproduce --result-json INDEX_DIR/results/result.json --output-dir reproduction
photo-cat merge-bright-stars data/gaia.csv data/bright.csv --output data/merged_catalog.csv
photo-cat screen INDEX_DIR/results/result.json --output screening.csv
photo-cat validate-results INDEX_DIR/results/result.json data/reference.csv --output validation.json --matched-output residuals.csv
```

`summarize` emits aggregate target counts, selected-contaminant counts,
all-neighbour counts, flux-fraction statistics, and separation statistics.
`plot` writes dependency-free SVG files for contaminant counts, flux fractions,
separations, or a simple RA/Dec sky map; `--backend matplotlib` enables richer
publication outputs, including area-normalized separations and
flux-vs-separation scatter plots. `export` writes flat CSV or Parquet target
tables. `report` writes an HTML, Markdown, or multi-page PDF document that bundles the summary
and plots. `provenance` records catalogue checksums and basic input statistics.
`benchmark` runs selected pipeline stages and records wall-clock time plus
Python `tracemalloc` peak allocations; if `psutil` is installed it also samples
native RSS memory. A shareable Markdown or CSV benchmark table can be
generated with `benchmark-table`. `reproduce` gathers result products and checksums into
a reproduction manifest. `merge-bright-stars` creates a de-duplicated
catalogue from a Gaia-like table plus a supplemental bright-star table.
`screen` creates a ranked, reasoned accept/review/reject decision table.
`validate-results` quantifies agreement with an external mission/reference
contamination table and can export matched residuals.
`publication-plots` generates a contaminant-count distribution, separation
distribution, and colourblind-safe sky map from the same single-aperture result.
It also produces an annular-area-normalized separation plot and records input
and output checksums in a manifest.

## Console output

The pipeline console shows:

- current pipeline stage
- progress bars
- result save path
- final target summary

The saved JSON path is highlighted in the console so it is easier to find after the run completes.
