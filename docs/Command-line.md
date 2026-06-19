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

`out_dir` must be a directory. It cannot reuse the path of an existing file. `KDTREE_FILENAME` must be a filename only; set `--out-dir` to choose the output folder.

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
| `build_neighbors_index.io.KDTREE_FILENAME` | `--kdtree-filename NAME` |
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
| `execution.run_build` | `--run-build` / `--no-run-build` |
| `execution.run_query` | `--run-query` / `--no-run-query` |
| `execution.replace_running_pipeline` | `--replace-running-pipeline` / `--no-replace-running-pipeline` |
