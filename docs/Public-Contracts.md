<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Public contracts

This document identifies PHOTO-CAT behaviour that contributors should preserve unless a release explicitly documents an intentional compatibility change.

It is not an API promise for every internal function. It defines the user-visible boundaries protected by regression tests.

## Command-line interface

The following commands and aliases are public:

```text
photo-cat configure
photo-cat gui
photo-cat run
photo-cat build-index
photo-cat query
photo-cat doctor
photo-cat --version
```

Documented command-line options, including direct runtime overrides, should retain their meaning. New options are allowed when they do not silently change existing command behaviour.

Expected user input failures should return status `1` and print a concise `ERROR:` message to standard error. Normal successful commands return status `0`.

## Configuration

The top-level sections in `config.yaml` are public:

```text
build_neighbors_index
query_contamination_from_index
execution
```

Documented keys inside these sections, relative-path behaviour, and validation rules are part of the supported configuration model. Additive settings are preferred over renaming or silently reinterpreting existing settings.

### Path-resolution rules

- Relative paths stored in `config.yaml`, including catalogue, targets, build-output, and query-index paths, resolve relative to the directory containing that config file.
- An explicit CLI `--config` path and direct CLI path overrides resolve relative to the working directory where `photo-cat` is invoked.
- Query result files are created only under `INDEX_DIR/output`; a file occupying that path is a validation error.
- Index directory validation happens before numerical query execution opens index arrays or memory maps.
- Reading or validating a configuration must not create output directories, change the caller working directory, or permanently modify `PHOTO_CAT_CONFIG`.
- Direct CLI overrides are derived for one command only and do not rewrite the source `config.yaml`.
- Pipeline child processes receive the selected config explicitly; repeated commands in one process must not inherit an earlier override.

## Build-index outputs

A successful build writes the documented neighbour-index files inside the configured output directory. Query mode relies on that directory layout, so changes require a migration plan, compatibility handling, or a documented major-version break.

## Query results

The query stage writes JSON files under `INDEX_DIR/output`.

Each target result preserves the documented fields for:

- target source ID;
- target coordinates and magnitude when available;
- `flux_fraction_extra`;
- `num_contaminants`;
- contaminant records including source ID, coordinates, magnitude, and separation.

Regression tests should protect field names, result ordering where documented, and numerical conventions that affect scientific interpretation.

## Diagnostics and launchers

`photo-cat doctor` supports both installed-package mode and source-project mode. Its documented success/failure status and practical diagnostics are user-facing behaviour.

The Windows and Unix launchers remain supported entry points for local non-technical use. Internal changes must not require users to understand the development virtual environment.

## Internal code may change

Private helper names, module organisation, dataclass layout, and implementation details may change when public behaviour is preserved. Unit tests may target those helpers, but regression tests should be the primary guard for the contracts above.

## Changing a contract

Before changing a public contract:

1. explain the compatibility impact in the pull request;
2. update English and Italian documentation;
3. update or add regression tests;
4. include migration notes where users may have existing configuration, index, or output files;
5. choose a version number consistent with the compatibility impact.
