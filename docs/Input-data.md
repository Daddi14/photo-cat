# Input data

PHOTO-CAT works with CSV input files.

## Catalogue CSV

The catalogue CSV is the main source table used to build the neighbour index.

The default expected columns are:

- `source_id`
- `ra`
- `dec`
- `phot_g_mean_mag`

`ra` and `dec` must be numeric coordinates. `phot_g_mean_mag` must be numeric if magnitude filtering is used.

## Targets CSV

The targets CSV identifies the sources to query against the built neighbour index.

The default target identifier column is:

- `source_id`

The target values must match IDs from the catalogue.

## Manual targets

PHOTO-CAT can also use a manual list of target source IDs instead of a targets CSV.

This is useful for quick checks or small target lists.

## Column names

Column names are case-sensitive. They must match the CSV header exactly.

If your catalogue uses different names, configure them in the graphical configurator before running the pipeline.

## Example files

Small example files are included in `data/`:

- `example_catalog.csv`
- `example_targets.csv`

These are only for testing the workflow. Replace them with real catalogue and target files for analysis.
