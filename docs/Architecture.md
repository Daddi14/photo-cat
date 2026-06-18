<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Architecture and testing boundaries

PHOTO-CAT is organised around stable public behaviour and replaceable internal implementation.

## Public interfaces

The following interfaces are treated as user-facing contracts:

- `photo-cat` and its documented subcommands.
- `config.yaml` section names and documented settings.
- The graphical configurator.
- Build-index output files.
- Query JSON output fields.
- `photo-cat doctor` package-install and project-folder modes.

Regression tests should protect these interfaces while internal code is split or improved.

## Pipeline stages

The runtime pipeline has three boundaries:

1. **Configuration** parses YAML, resolves paths, and validates setting types and ranges.
2. **Build/index** loads the catalogue and creates the resumable neighbour index.
3. **Query/contamination** reads the index and produces contamination results for configured targets.

`config_and_run.py` is intentionally limited to pipeline orchestration. It resolves which stages are enabled and invokes the build and query modules; it does not perform scientific calculations itself.

## Module responsibility map

| Module | Current responsibility | Contract risk during refactoring |
|---|---|---|
| `load_config.py` | Parse YAML, resolve documented paths, and validate typed configuration dataclasses. | Configuration keys, defaults, relative-path rules, and validation messages. |
| `cli.py` and `cli_overrides.py` | Parse documented CLI commands and create temporary runtime overrides. | Command names, options, exit statuses, and `ERROR:` convention. |
| `config_and_run.py` | Select and invoke enabled pipeline stages. | Build-before-query ordering and stage flags. |
| `build_neighbors_index.py` | Load catalogues and create the reusable neighbour index. | Index directory layout and numerical neighbour conventions. |
| `query_contamination_from_index.py` | Read an index and write target contamination JSON results. | JSON result fields, target-ID handling, and flux/separation conventions. |
| `doctor.py` | Report package and source-project diagnostics. | Package-install and project-folder diagnostic behaviour. |

Future refactoring should start by extracting one focused responsibility from a module, then protect its surrounding public boundary with regression tests. Path policy remains a candidate for further separation from runtime execution where it creates clearer testable boundaries.

## Testing strategy

Tests are grouped by intent:

- **Regression tests** (`@pytest.mark.regression`) protect public CLI, pipeline, and result behaviour.
- **Unit tests** (`@pytest.mark.unit`) target pure helpers such as path/config validation, coordinate conversions, ID resolution, and flux calculations.
- **Integration tests** use the bundled example catalogue and targets to verify that the build and query stages work together.
- **Coverage reports** identify untested paths; they guide prioritisation but do not replace behavioural assertions.

Shared temporary inputs belong in `tests/conftest.py`. Each test is explicitly classified with `@pytest.mark.regression` or `@pytest.mark.unit`; CI uses strict marker handling. Tests should include a docstring when the expected result depends on a scientific rule, a numerical convention, or a non-obvious compatibility behaviour. See [Development workflow](Development.md) and [Public contracts](Public-Contracts.md) for the contributor-facing rules.

## Refactoring guidance

Refactoring should preserve public contracts first. Prefer extracting a focused helper from a large function, adding unit coverage for it, and then simplifying its caller. Do not introduce a design pattern solely for its name: Strategy or Chain of Responsibility should be adopted only when multiple real execution or validation policies need interchangeable implementations.
