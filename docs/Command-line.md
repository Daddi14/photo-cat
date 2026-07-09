# Command-line usage

PHOTO-CAT can be run from the command line with a YAML configuration file and optional direct CLI overrides.

The GUI remains the recommended entry point for normal desktop use. The CLI is intended for scripted runs, remote systems, clusters, repeatable pipelines, and batch workflows.

## Basic commands

```bash
photo-cat --help
photo-cat configure
photo-cat run --config config.yaml
photo-cat build-index --config config.yaml
photo-cat query --config config.yaml
photo-cat summarize output/index/output/result.json
photo-cat export output/index/output/result.json --format csv --output output/result.csv
photo-cat plot output/index/output/result.json --kind contaminant-counts
photo-cat report output/index/output/result.json --format html
photo-cat benchmark --config config.yaml --output output/benchmark.json
photo-cat provenance data/catalog.csv --output output/catalog_provenance.json
photo-cat doctor
```

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
photo-cat summarize output/my_index/output/result.json
photo-cat summarize output/my_index/output/result.json --format json --output output/summary.json
photo-cat summarize output/my_index/output/result.json --format csv --output output/summary.csv
```

Create SVG plots without optional plotting dependencies:

```bash
photo-cat plot output/my_index/output/result.json --kind contaminant-counts --output output/counts.svg
photo-cat plot output/my_index/output/result.json --kind flux --output output/flux.svg
photo-cat plot output/my_index/output/result.json --kind separations --output output/separations.svg
photo-cat plot output/my_index/output/result.json --kind sky-map --output output/sky-map.svg
photo-cat plot output/my_index/output/result.json --kind sky-map --backend matplotlib --output output/sky-map.png
```

Export flat target tables:

```bash
photo-cat export output/my_index/output/result.json --format csv --output output/result.csv
photo-cat export output/my_index/output/result.json --format parquet --output output/result.parquet
```

Create a compact report:

```bash
photo-cat report output/my_index/output/result.json --format html --output output/report.html
photo-cat report output/my_index/output/result.json --format markdown --output output/report.md
```

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
photo-cat provenance data/my_catalog.csv --adql-file examples/paper/gaia_dr3_g17_selection.adql --output output/catalog_provenance.json
```

Provenance JSON includes the catalogue path, SHA-256, byte size, row count,
columns, null counts, numeric ranges for RA/Dec/magnitude columns, duplicate
source-ID count, and optional ADQL/query-file checksum.

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

For `photo-cat query`, the selected index folder must contain the completed index files. The query result path is created under `INDEX_DIR/output`; a file named `output` in that folder is treated as an error rather than being overwritten.

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
  --max-radius-arcsec 120 ^
  --field-of-view-arcsec 47 ^
  --delta-mag 5 ^
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
| `query_contamination_from_index.settings.delta_mag` | `--delta-mag VALUE` |
| `query_contamination_from_index.settings.include_missing_targets` | `--include-missing-targets` / `--no-include-missing-targets` |
| `execution.run_build` | `--run-build` / `--no-run-build` |
| `execution.run_query` | `--run-query` / `--no-run-query` |
| `execution.replace_running_pipeline` | `--replace-running-pipeline` / `--no-replace-running-pipeline` |
