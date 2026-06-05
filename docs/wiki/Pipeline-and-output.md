# Pipeline and output

PHOTO-CAT has two main pipeline stages.

## Stage 1: Build neighbour index

The build stage reads the catalogue, validates the configured columns, converts coordinates, and builds an index of neighbouring sources.

Generated index files are written to the configured index/output directory.

## Stage 2: Query contamination

The query stage loads the index and processes the selected targets.

For each target, PHOTO-CAT identifies neighbouring sources inside the configured field of view and applies the configured magnitude criteria.

## Output JSON

The query stage writes a JSON result file to the configured output folder.

Each target result includes:

- target source ID
- target coordinates
- target magnitude, when available
- extra flux fraction
- number of contaminants
- contaminant source list
- contaminant coordinates, magnitudes, and separations

## Console output

The pipeline console shows:

- current pipeline stage
- progress bars
- result save path
- final target summary

The saved JSON path is highlighted in the console so it is easier to find after the run completes.
