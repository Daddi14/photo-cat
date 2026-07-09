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
- `delta_mag` is the maximum allowed catalogue magnitude difference,
  `mag_neighbour - mag_target`, for a neighbour to be selected.
- A `contaminant` in the JSON output means a neighbour that passes both the
  configured circular-radius cut and the `delta_mag` cut.
- `flux_fraction_selected` is computed from the same selected contaminants as
  `num_contaminants`, using catalogue magnitude ratios
  `10 ** (-0.4 * (mag_neighbour - mag_target))`, and is reported as a
  percentage of the target flux.
- `flux_fraction_all_neighbors` uses every valid neighbour inside the circular
  query radius, even if it does not pass `delta_mag`.
- `flux_fraction_extra` is retained as a backward-compatible alias of
  `flux_fraction_selected`.

The current implementation does not perform instrumental PSF convolution,
detector-pixel response modelling, aperture weighting, wavelength-dependent
bandpass transformations, or non-uniform scattered-light modelling from bright
sources just outside the configured radius. Those effects require
mission-specific inputs and should not be inferred from PHOTO-CAT's current
catalogue-only metrics.

## Output JSON

The query stage writes a JSON result file to the configured output folder.

Each target result includes:

- target source ID
- target coordinates
- target magnitude, when available
- selected-contaminant flux fraction
- all-neighbour-in-radius flux fraction
- number of neighbours inside the circular radius
- number of selected contaminants
- contaminant source list
- contaminant coordinates, magnitudes, and separations

For reproducibility, each query also writes a sidecar metadata JSON file under
`INDEX_DIR/output/metadata/`. The sidecar records the PHOTO-CAT version, selected
configuration values, target count, index manifest, catalogue SHA-256 from the
index build, and the model-scope notes above. The target-result JSON remains a
plain list of target entries for compatibility with existing scripts.

## Derived summaries, plots, reports, and benchmarks

After a query, result files can be converted into reproducible paper-style
products:

```bash
photo-cat summarize INDEX_DIR/output/result.json --format json --output summary.json
photo-cat plot INDEX_DIR/output/result.json --kind contaminant-counts --output counts.svg
photo-cat plot INDEX_DIR/output/result.json --kind separations --output separations.svg
photo-cat plot INDEX_DIR/output/result.json --kind sky-map --output sky-map.svg
photo-cat report INDEX_DIR/output/result.json --format html --output report.html
photo-cat benchmark --config config.yaml --output benchmark.json
```

`summarize` emits aggregate target counts, selected-contaminant counts,
all-neighbour counts, flux-fraction statistics, and separation statistics.
`plot` writes dependency-free SVG files for contaminant counts, flux fractions,
separations, or a simple RA/Dec sky map. `report` writes an HTML or Markdown
document that bundles the summary and plots. `benchmark` runs selected pipeline
stages and records wall-clock time plus Python `tracemalloc` peak allocations;
native memory used by NumPy/SciPy may be higher than the Python allocation
counter.

## Console output

The pipeline console shows:

- current pipeline stage
- progress bars
- result save path
- final target summary

The saved JSON path is highlighted in the console so it is easier to find after the run completes.
