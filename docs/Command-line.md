# Command-line usage

PHOTO-CAT can be run from the command line with a YAML configuration file and optional direct CLI overrides.

The GUI remains the recommended entry point for normal desktop use. The CLI is intended for scripted runs, remote systems, clusters, repeatable pipelines, and batch workflows.

## Language

Use the global `--language` option before the command to select English or Italian help and messages:

```bash
photo-cat --language it --help
photo-cat --language it doctor
photo-cat --language it run --config config.yaml
```

The explicit option takes precedence. Otherwise PHOTO-CAT uses `PHOTO_CAT_LANGUAGE`, then `interface.language` from the selected configuration, and finally English. Command names, option names, machine-readable schema keys, and scientific plot labels remain stable and in English.

## Basic commands

```bash
photo-cat --help
photo-cat configure
photo-cat run --config config.yaml
photo-cat build-index --config config.yaml
photo-cat query --config config.yaml
photo-cat summarize output/index/results/result.json
photo-cat export output/index/results/result.json --format csv --output output/result.csv
photo-cat plot output/index/results/result.json --kind contaminant-counts
photo-cat publication-plots output/index/results/result.json --aperture-arcsec 47 --output-dir output/publication_plots
photo-cat report output/index/results/result.json --format html
photo-cat screen output/index/results/result.json --output output/screening.csv
photo-cat validate-results output/index/results/result.json data/reference.csv --output output/validation.json
photo-cat benchmark --config config.yaml --output output/benchmark.json
photo-cat benchmark-table output/benchmark.json --output output/benchmark_table.md
photo-cat provenance data/catalog.csv --output output/catalog_provenance.json
photo-cat reproduce --config examples/reproducibility/config_47arcsec.yaml --output-dir output/reproduction
photo-cat merge-bright-stars data/gaia.csv data/bright.csv --output data/merged_catalog.csv
photo-cat doctor
```

`screen` (alias `rank`) orders targets by a selected contamination metric and
assigns `accept`, `review`, or `reject` using explicit percentage thresholds.
`validate-results` (alias `validate`) joins an external reference contamination
CSV by source ID and reports bias, median residual, MAE, RMSE, and optional
threshold-classification accuracy.

`publication-plots` generates a coordinated publication plot set from one
result JSON and the aperture represented by that result. It writes:

- a contaminant-count distribution with logarithmic Y and zero-safe
  symmetric-log X scaling;
- the raw separation distribution and an additional annular-area
  normalized version;
- an RA/Dec contamination map using blue/yellow/purple plus distinct
  circle/triangle/X markers and sizes, so class meaning never relies on colour
  alone;
- a checksummed `publication_plots_manifest.json`.

PNG, PDF, and SVG outputs are supported through `--format`.

When a bandpass profile was used, screen or validate its mission-band estimate
with `--metric flux_fraction_total_weighted_transformed`.

## Doctor diagnostics for automation

`photo-cat doctor` prints a readable diagnostic report by default:

```bash
photo-cat doctor
```

Automation can request one machine-readable JSON document instead:

```bash
photo-cat doctor --format json
```

The JSON report uses schema version `1` and contains these stable top-level fields:

```json
{
  "schema_version": 1,
  "ok": true,
  "checks": [
    {
      "name": "python",
      "status": "pass",
      "message": "Python",
      "detail": "3.13.0"
    }
  ],
  "summary": {
    "passed": 1,
    "warnings": 0,
    "failed": 0,
    "information": 0
  }
}
```

`status` is one of `pass`, `warn`, `fail`, or `info`. The command returns `0` when no checks fail and `1` when one or more checks fail. Warnings remain visible in JSON but do not change a successful exit status. The default `text` format remains unchanged for interactive use.

## Configuration file model

The standard command reads values from `config.yaml`:

```bash
photo-cat run --config config.yaml
```

CLI overrides can replace any value from the YAML file for that run only:

```bash
photo-cat run --config config.yaml --delta-mag 4.0 --field-of-view-arcsec 60.0
```

Overrides do not permanently edit `config.yaml`. PHOTO-CAT writes a temporary runtime config, runs the requested command, and removes the temporary file afterward.

## Reproducible run recipe

For analyses that need to be reviewed or rerun, save the exact commands and
inputs used to create the catalogue CSV and PHOTO-CAT outputs. A minimal
PHOTO-CAT command sequence is:

```bash
photo-cat --version
photo-cat build-index --config config.yaml --input-catalog data/my_catalog.csv --out-dir output/my_index --max-radius-arcsec 120
photo-cat query --config config.yaml --index-dir output/my_index --targets-input data/my_targets.csv --field-of-view-arcsec 47 --delta-mag 5
photo-cat query --config config.yaml --bandpass-transform-file examples/reproducibility/bandpass_transform_example.yaml
```

The build writes `index_manifest.json` with the catalogue SHA-256 and build
settings that define the neighbour index. The query writes the target-result
JSON plus a metadata sidecar under `output/my_index/output/metadata/` with the
PHOTO-CAT version, query settings, index manifest, processed target count, and
model-scope notes. Keep those files with the catalogue-selection query or
notebook that generated `data/my_catalog.csv`.

## Summaries, exports, plots, reports, provenance, and benchmarks

Summarize one query result:

```bash
photo-cat summarize output/my_index/results/result.json
photo-cat summarize output/my_index/results/result.json --format json --output output/summary.json
photo-cat summarize output/my_index/results/result.json --format csv --output output/summary.csv
```

Create SVG plots without optional plotting dependencies:

```bash
photo-cat plot output/my_index/results/result.json --kind contaminant-counts --output output/counts.svg
photo-cat plot output/my_index/results/result.json --kind flux --output output/flux.svg
photo-cat plot output/my_index/results/result.json --kind separations --output output/separations.svg
photo-cat plot output/my_index/results/result.json --kind separations-normalized --output output/separations_area_norm.svg
photo-cat plot output/my_index/results/result.json --kind flux-vs-separation --output output/flux_vs_separation.svg
photo-cat plot output/my_index/results/result.json --kind contamination-vs-magnitude --output output/contamination_vs_magnitude.svg
photo-cat plot output/my_index/results/result.json --kind sky-map --output output/sky-map.svg
photo-cat plot output/my_index/results/result.json --kind sky-map --format png --output output/sky-map.png
photo-cat plot output/my_index/results/result.json --kind sky-map --format pdf --output output/sky-map.pdf
```

`plot --format` accepts `svg`, `png`, or `pdf`. PNG and PDF automatically use matplotlib; SVG retains the lightweight built-in renderer unless `--backend matplotlib` is selected explicitly.

Export flat target tables:

```bash
photo-cat export output/my_index/results/result.json --format csv --output output/result.csv
photo-cat export output/my_index/results/result.json --format parquet --output output/result.parquet
```

Create a compact report:

```bash
photo-cat report output/my_index/results/result.json --format html --output output/report.html
photo-cat report output/my_index/results/result.json --format markdown --output output/report.md
photo-cat report output/my_index/results/result.json --format pdf --output output/report.pdf
```

The PDF contains a summary page followed by diagnostic plot pages. Use HTML for local browser viewing, Markdown for repository/review text, and PDF for a single shareable or submission-ready document.

Record benchmark metadata:

```bash
photo-cat benchmark --config config.yaml --output output/benchmark.json
photo-cat benchmark --config config.yaml --no-run-build --run-query --output output/query_benchmark.json
```

Benchmark JSON includes PHOTO-CAT version, Python/platform metadata, selected
stage durations, status codes, and Python `tracemalloc` peak allocations. The
allocation counter is reproducible and dependency-free. If `psutil` is installed,
the benchmark also samples native RSS memory; otherwise RSS fields are present
but marked unavailable.

Capture catalogue provenance:

```bash
photo-cat provenance data/my_catalog.csv --adql-file examples/reproducibility/gaia_dr3_g17_selection.adql --output output/catalog_provenance.json
```

Provenance JSON includes the catalogue path, SHA-256, byte size, row count,
columns, null counts, numeric ranges for RA/Dec/magnitude columns, duplicate
source-ID count, and optional ADQL/query-file checksum.

Use `provenance` when a catalogue is downloaded, filtered, merged, or prepared for a release. It answers “exactly which input table and selection did this run use?” and lets collaborators detect a changed file. Run it again whenever the catalogue or ADQL selection changes. It does not test whether contamination predictions are scientifically accurate.

Validate predictions against an independent reference:

```bash
photo-cat validate-results output/my_index/results/result.json data/reference.csv --reference-column contamination_percent --output output/validation.json --matched-output output/residuals.csv
```

Use `validate-results` only when an external measured or independently modelled contamination table exists. The reference should use a comparable aperture, bandpass, target IDs, and percentage definition. It answers “how closely do PHOTO-CAT predictions agree with the reference?” through bias, median residual, MAE, RMSE, and optional threshold accuracy. It does not establish absolute accuracy when the reference is not physically comparable.

Generate reproducible products from existing results or reproducible configs:

```bash
photo-cat reproduce --result-json output/my_index/results/result.json --output-dir output/reproduction
photo-cat reproduce --config examples/reproducibility/config_47arcsec.yaml --config examples/reproducibility/config_75arcsec.yaml --output-dir output/reproduction
photo-cat reproduce --config config.yaml --run-configs --output-dir output/reproduction
```

The command copies configs/results, writes summaries, plots, HTML reports, and
`paper_reproduction_manifest.json` with checksums.

Merge a supplemental bright-star CSV into a Gaia-like catalogue before building
an index:

```bash
photo-cat merge-bright-stars data/gaia.csv data/bright_stars.csv --output data/merged_catalog.csv --provenance-output output/merge_provenance.json
```

Duplicate source IDs are de-duplicated with `--prefer bright` by default.

## Path handling

Paths provided through CLI overrides are resolved relative to the current working directory.

Example:

```bash
photo-cat run --config configs/run.yaml --input-catalog data/catalog.csv
```

`data/catalog.csv` is resolved from the folder where the command is executed.

## Input and output errors

CLI commands return a non-zero status and print an `ERROR:` message to standard error when a configuration file, catalogue, targets CSV, index folder, or output path is invalid.

Examples:

```bash
photo-cat build-index --config missing.yaml
photo-cat build-index --config config.yaml --input-catalog data/missing_catalog.csv
```

`out_dir` must be a directory. It cannot reuse the path of an existing file.

For `photo-cat query`, the selected index folder must contain the completed index files. The query result path is created under `INDEX_DIR/results`; a file named `results` in that folder is treated as an error rather than being overwritten.

## Full pipeline with direct overrides

```bash
photo-cat run ^
  --config config.yaml ^
  --input-catalog data/my_catalog.csv ^
  --targets-input data/my_targets.csv ^
  --out-dir output/my_run ^
  --index-dir output/my_run ^
  --catalog-source-id-column source_id ^
  --ra-column ra ^
  --dec-column dec ^
  --mag-column phot_g_mean_mag ^
  --magnitude-columns gaia_g=phot_g_mean_mag,gaia_bp=phot_bp_mean_mag,gaia_rp=phot_rp_mean_mag ^
  --max-radius-arcsec 120 ^
  --field-of-view-arcsec 47 ^
  --delta-mag 5 ^
  --contamination-bands gaia_g,gaia_bp,gaia_rp ^
  --contamination-model-mode top_hat ^
  --chunk-size 10000 ^
  --buffer-flush-interval 200 ^
  --use-dask ^
  --no-calculate-separations ^
  --run-build ^
  --run-query
```

On macOS/Linux, use backslashes instead of `^` for line continuation:

```bash
photo-cat run \
  --config config.yaml \
  --input-catalog data/my_catalog.csv \
  --targets-input data/my_targets.csv \
  --out-dir output/my_run \
  --index-dir output/my_run \
  --ra-column ra \
  --dec-column dec \
  --mag-column phot_g_mean_mag \
  --field-of-view-arcsec 47 \
  --delta-mag 5
```

## Catalogue column override example

If the catalogue has these headers:

```text
id,RAJ2000,DEJ2000,Gmag
```

run:

```bash
photo-cat run --config config.yaml ^
  --input-catalog data/catalog.csv ^
  --targets-input data/targets.csv ^
  --catalog-source-id-column id ^
  --ra-column RAJ2000 ^
  --dec-column DEJ2000 ^
  --mag-column Gmag
```

## Query-only example

Use this when the index already exists and only query settings or targets changed:

```bash
photo-cat query --config config.yaml ^
  --index-dir output/my_run ^
  --targets-input data/new_targets.csv ^
  --target-source-id-column source_id ^
  --field-of-view-arcsec 60 ^
  --delta-mag 4
```

## Manual targets without a targets CSV

Use `--no-targets-input` with `--targets`:

```bash
photo-cat query --config config.yaml ^
  --index-dir output/my_run ^
  --no-targets-input ^
  --targets 1001,1002,1003 ^
  --field-of-view-arcsec 47 ^
  --delta-mag 5
```

For target IDs containing spaces, quote the argument:

```bash
photo-cat query --config config.yaml --no-targets-input --targets "HD 216608A,HD 216608B"
```

## Build-only example

Use this when the catalogue or build radius changed:

```bash
photo-cat build-index --config config.yaml ^
  --input-catalog data/catalog.csv ^
  --out-dir output/index_120arcsec ^
  --catalog-source-id-column source_id ^
  --ra-column ra ^
  --dec-column dec ^
  --mag-column phot_g_mean_mag ^
  --max-radius-arcsec 120 ^
  --chunk-size 50000 ^
  --use-dask
```

## Skip build or query in full pipeline

Run query only through the pipeline command:

```bash
photo-cat run --config config.yaml --no-run-build --run-query
```

Run build only through the pipeline command:

```bash
photo-cat run --config config.yaml --run-build --no-run-query
```

## Boolean override syntax

Boolean options support positive and negative forms:

```bash
--use-dask
--no-use-dask
--calculate-separations
--no-calculate-separations
--run-build
--no-run-build
--run-query
--no-run-query
--replace-running-pipeline
--no-replace-running-pipeline
```

## Complete override reference

| YAML value | CLI override |
|---|---|
| `build_neighbors_index.io.input_catalog` | `--input-catalog PATH` |
| `build_neighbors_index.io.out_dir` | `--out-dir PATH` |
| `build_neighbors_index.io.usecolumns` | `--usecolumns source_id,ra,dec,mag` |
| `build_neighbors_index.io.columns.source_id` | `--catalog-source-id-column NAME` |
| `build_neighbors_index.io.columns.ra` | `--ra-column NAME` |
| `build_neighbors_index.io.columns.dec` | `--dec-column NAME` |
| `build_neighbors_index.io.columns.phot_g_mean_mag` | `--mag-column NAME` |
| `build_neighbors_index.settings.use_dask` | `--use-dask` / `--no-use-dask` |
| `build_neighbors_index.settings.calculate_separations` | `--calculate-separations` / `--no-calculate-separations` |
| `build_neighbors_index.settings.max_radius_arcsec` | `--max-radius-arcsec VALUE` |
| `build_neighbors_index.settings.chunk_size` | `--chunk-size VALUE` |
| `build_neighbors_index.settings.buffer_flush_interval` | `--buffer-flush-interval VALUE` |
| `query_contamination_from_index.io.INDEX_DIR` | `--index-dir PATH` |
| `query_contamination_from_index.io.TARGETS_INPUT` | `--targets-input PATH` or `--no-targets-input` |
| `query_contamination_from_index.io.targets` | `--targets ID1,ID2,ID3` |
| `query_contamination_from_index.io.target_source_id_column` | `--target-source-id-column NAME` |
| `query_contamination_from_index.settings.field_of_view_arcsec` | `--field-of-view-arcsec VALUE` |
| `query_contamination_from_index.settings.field_of_view_arcsec` | `--aperture-radius-arcsec VALUE` (clearer alias) |
| `query_contamination_from_index.settings.influence_radius_arcsec` | `--influence-radius-arcsec VALUE` |
| `query_contamination_from_index.settings.bandpass_transform_file` | `--bandpass-transform-file PATH` |
| `query_contamination_from_index.settings.delta_mag` | `--delta-mag VALUE` |
| `query_contamination_from_index.settings.include_missing_targets` | `--include-missing-targets` / `--no-include-missing-targets` |
| `execution.run_build` | `--run-build` / `--no-run-build` |
| `execution.run_query` | `--run-query` / `--no-run-query` |
| `execution.replace_running_pipeline` | `--replace-running-pipeline` / `--no-replace-running-pipeline` |
