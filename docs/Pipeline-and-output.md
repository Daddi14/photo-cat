# Pipeline and output

PHOTO-CAT has two main pipeline stages.

## Stage 1: Build neighbour index

The build stage reads the catalogue, validates the configured columns, converts coordinates, and builds an index of neighbouring sources.

Generated index files are written to the configured index/output directory.
Format version 2 indexes include `index_manifest.json`, which records the
catalogue fingerprint, build radius, source count, and completion state.
Checkpoints and final files are published atomically so interrupted builds can
resume without appending uncommitted records.

Indexes built by PHOTO-CAT 1.x must be rebuilt. Version 2 does not load the
legacy pickle/object-array format. The obsolete `KDTREE_FILENAME` config key is
ignored, and the `--kdtree-filename` CLI option has been removed.

## Stage 2: Query contamination

The query stage loads the index and processes the selected targets.

For each target, PHOTO-CAT identifies neighbouring sources inside the configured
circular query radius (`field_of_view_arcsec`) and applies the configured
magnitude criteria. The query is rejected if this radius is larger than the
radius represented by the index. The extra-flux metric and contaminant list use
the same radius and magnitude selection.

## Contamination model and terminology

PHOTO-CAT 2.0.0 reports catalogue-level, aperture-like contamination metrics.
It is best interpreted as a contamination risk-assessment or target-screening
tool unless mission-specific modelling is added downstream.

- `field_of_view_arcsec` is the circular angular radius used by the query to
  select neighbours around each target. Despite the historical config key name,
  it is not automatically a detector field of view, PSF width, extraction
  aperture, or pixel scale; use the value that matches the screening aperture
  you want to test.
- `influence_radius_arcsec` is an optional larger neighbour-search radius used
  by weighted models to estimate flux leaking in from outside the aperture. It
  defaults to the aperture radius and must remain within the built index radius.
- `delta_mag` is the maximum allowed catalogue magnitude difference,
  `mag_neighbour - mag_target`, for a neighbour to be selected.
- A `contaminant` in the JSON output means a neighbour that passes both the
  configured circular-radius cut and the `delta_mag` cut.
- `contamination_model` records the query weighting mode. `top_hat` is the
  historical unweighted circular-aperture estimate. `gaussian_psf` applies a
  Gaussian radial point-response weight from the configured FWHM,
  `gaussian_aperture` integrates a circular Gaussian over the offset circular
  aperture, and `radial_weight` applies a user-supplied `sep_arcsec,weight` table.
- `flux_fraction_selected` is computed from the same selected contaminants as
  `num_contaminants`, using catalogue magnitude ratios
  `10 ** (-0.4 * (mag_neighbour - mag_target))`, and is reported as a
  percentage of the target flux.
- `flux_fraction_all_neighbors` uses every valid neighbour inside the circular
  query radius, even if it does not pass `delta_mag`.
- `flux_fraction_extra` is retained as a backward-compatible alias of
  `flux_fraction_selected`.

The optional Gaussian/tabulated weights remain circular radial models, not full
instrument simulations. They can estimate leakage from sources between the
aperture and influence radii, but do not model asymmetric or spatially varying
PSFs, detector pixels, diffraction or scattered light. A versioned empirical
colour-polynomial profile can estimate a mission-band magnitude, but PHOTO-CAT
does not perform full spectral-energy-distribution or passband integration.

## Output JSON

The query stage writes a JSON result file to the configured output folder.

Each target result includes:

- target source ID
- target coordinates
- target magnitude, when available
- selected-contaminant flux fraction
- all-neighbour-in-radius flux fraction
- optional per-band selected/all-neighbour flux-fraction dictionaries
- optional transformed mission-band metrics, target/contaminant magnitudes,
  and per-target validity status
- weighted inside-aperture, outside-aperture, and total flux fractions
- outside-aperture neighbour counts and selected-source records
- number of neighbours inside the circular radius
- number of selected contaminants
- contaminant source list
- contaminant coordinates, magnitudes, and separations

For reproducibility, each query also writes a sidecar metadata JSON file under
`INDEX_DIR/output/metadata/`. The sidecar records the PHOTO-CAT version, selected
configuration values, target count, index manifest, catalogue SHA-256 from the
index build, optional bandpass-profile checksum, and the model-scope notes
above. The target-result JSON remains a
plain list of target entries for compatibility with existing scripts.

By default, target IDs that are invalid or absent from the index are skipped with
warnings. Set `include_missing_targets: true` or pass `--include-missing-targets`
to preserve those requested IDs as JSON rows with `status` set to
`missing_from_index` or `invalid_target_id` and science metrics set to `null`.

## Derived summaries, plots, reports, and benchmarks

After a query, result files can be converted into reproducible paper-style
products:

```bash
photo-cat summarize INDEX_DIR/output/result.json --format json --output summary.json
photo-cat export INDEX_DIR/output/result.json --format csv --output result.csv
photo-cat plot INDEX_DIR/output/result.json --kind contaminant-counts --output counts.svg
photo-cat plot INDEX_DIR/output/result.json --kind sky-map --backend matplotlib --output sky-map.png
photo-cat plot INDEX_DIR/output/result.json --kind separations-normalized --output separations_area_norm.svg
photo-cat plot INDEX_DIR/output/result.json --kind flux-vs-separation --output flux_vs_separation.svg
photo-cat plot INDEX_DIR/output/result.json --kind sky-map --output sky-map.svg
photo-cat report INDEX_DIR/output/result.json --format html --output report.html
photo-cat provenance data/catalog.csv --output catalog_provenance.json
photo-cat benchmark --config config.yaml --output benchmark.json
photo-cat benchmark-table benchmark.json --output benchmark_table.md
photo-cat reproduce-paper --result-json INDEX_DIR/output/result.json --output-dir paper_products
photo-cat merge-bright-stars data/gaia.csv data/bright.csv --output data/merged_catalog.csv
photo-cat screen INDEX_DIR/output/result.json --output screening.csv
photo-cat validate-results INDEX_DIR/output/result.json data/reference.csv --output validation.json --matched-output residuals.csv
```

`summarize` emits aggregate target counts, selected-contaminant counts,
all-neighbour counts, flux-fraction statistics, and separation statistics.
`plot` writes dependency-free SVG files for contaminant counts, flux fractions,
separations, or a simple RA/Dec sky map; `--backend matplotlib` enables richer
plots when matplotlib is installed, including area-normalized separations and
flux-vs-separation scatter plots. `export` writes flat CSV or Parquet target
tables. `report` writes an HTML or Markdown document that bundles the summary
and plots. `provenance` records catalogue checksums and basic input statistics.
`benchmark` runs selected pipeline stages and records wall-clock time plus
Python `tracemalloc` peak allocations; if `psutil` is installed it also samples
native RSS memory. A paper-ready Markdown or CSV benchmark table can be
generated with `benchmark-table`. `reproduce-paper` gathers result products and checksums into
a paper reproduction manifest. `merge-bright-stars` creates a de-duplicated
catalogue from a Gaia-like table plus a supplemental bright-star table.
`screen` creates a ranked, reasoned accept/review/reject decision table.
`validate-results` quantifies agreement with an external mission/reference
contamination table and can export matched residuals.

## Console output

The pipeline console shows:

- current pipeline stage
- progress bars
- result save path
- final target summary

The saved JSON path is highlighted in the console so it is easier to find after the run completes.
