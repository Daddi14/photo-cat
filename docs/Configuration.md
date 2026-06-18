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

## Query stage

The query stage reads an existing index and processes selected targets.

Use this when the index already exists and you only need to query targets or adjust query options.

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

The YAML file is not permanently modified. For all available override flags and examples, see [Command-line usage](Command-line.md).
