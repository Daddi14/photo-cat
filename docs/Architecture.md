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

The runtime pipeline has five explicit boundaries:

1. **Configuration document loading** reads YAML and establishes the config-file directory without creating runtime folders or opening scientific resources.
2. **Derived configuration** applies CLI overrides to a deep-copied mapping, leaving the loaded document unchanged.
3. **Parsing and runtime validation** creates typed settings, validates files and directories, and resolves named paths before stage execution.
4. **Build/index** loads the catalogue and creates the resumable neighbour index.
5. **Query/contamination** validates index paths, then opens arrays and produces contamination results for configured targets.

`config_and_run.py` is intentionally limited to pipeline orchestration. It resolves which stages are enabled and invokes the build and query modules with an explicit config path; it does not change the caller working directory or perform scientific calculations itself.

## Module responsibility map

| Module | Current responsibility | Contract risk during refactoring |
|---|---|---|
| `path_policy.py` | Resolve non-GUI runtime paths, validate filesystem boundaries, and name index/query files. | Relative-path rules, output containment, and index-directory layout. |
| `load_config.py` | Load isolated YAML documents, parse typed settings, and separately validate runtime inputs using the shared path policy. | Configuration keys, defaults, validation messages, config-relative paths, and no state leakage between loads. |
| `cli.py` and `cli_overrides.py` | Parse documented CLI commands, derive disposable override configs, and scope legacy GUI environment state. | Command names, options, working-directory-relative overrides, exit statuses, `ERROR:` convention, and override isolation. |
| `config_and_run.py` | Select enabled stages and pass one explicit config path to child processes. | Build-before-query ordering, stage flags, and caller environment/working-directory isolation. |
| `build_neighbors_index.py` | Load catalogues and create the reusable neighbour index. | Index directory layout and numerical neighbour conventions. |
| `query_contamination_from_index.py` | Read an index and write target contamination JSON results. | JSON result fields, target-ID handling, and flux/separation conventions. |
| `doctor.py` | Report package and source-project diagnostics. | Package-install and project-folder diagnostic behaviour. |

Future refactoring should start by extracting one focused responsibility from a module, then protect its surrounding public boundary with regression tests. The path policy is now separated from non-GUI runtime execution: configuration and CLI callers resolve paths against an explicit base directory, while query execution consumes named, validated `IndexPaths` rather than rebuilding index filenames inline.

## Configuration lifecycle boundary

Configuration state is intentionally isolated from runtime execution:

- `load_configuration_document()` reads one YAML mapping and records the directory used for config-relative paths. It does not create folders, open index arrays, or mutate process environment state.
- Section readers return deep copies, so parsing one section or deriving CLI overrides cannot modify another later load.
- `load_config(..., validate_runtime=False)` supports parsing and typed validation without checking input files; the default runtime mode then validates required files and output targets before work starts.
- CLI overrides create a disposable YAML file only when required to retain the existing file-based module interface. The parent `PHOTO_CAT_CONFIG` environment value is not changed.
- Pipeline child processes receive the selected config through a copied child environment. The parent process keeps its original working directory and environment.

This lifecycle makes repeated commands in one Python process deterministic and keeps resource creation after parsing and validation boundaries.

## Path policy boundary

Path resolution is deliberately separate from scientific and pipeline execution:

- Paths written inside `config.yaml` resolve relative to the directory containing that configuration file.
- Explicit CLI `--config` paths and direct CLI path overrides resolve relative to the working directory where `photo-cat` is invoked.
- `path_policy.py` owns expansion, absolute resolution, file/directory validation, index layout naming, and controlled query-output placement.
- The query module validates an `IndexPaths` object before opening memory maps or performing numerical work.

This keeps filesystem rules independently testable and avoids changing the process working directory merely to interpret a path.

## Responsibility review

The v1.6.0 review applies the practical parts of SOLID without adding patterns solely for their names:

- **Single responsibility:** `load_config.py` now separates document loading, section parsing, and runtime-input validation; `path_policy.py` owns explicit runtime-directory creation; query setup prepares validated paths before numerical processing.
- **Explicit dependency direction:** CLI code passes a config path into runtime modules. Pipeline code passes that path only to child-process environments, instead of depending on a parent-process environment mutation.
- **Stable public boundary:** build, query, and diagnostics continue to expose the same documented commands, config keys, result layout, and error conventions.
- **Remaining concentrated responsibilities:** GUI persistence, build checkpoint/final-output persistence, query target parsing/JSON persistence, and installer/doctor operational checks remain the next candidates for isolated work.

Strategy and Chain of Responsibility are still not justified: the current code has one build mode, one query mode, and one ordered validation lifecycle rather than interchangeable policies.

## Remaining refactoring map

The following candidates are identified for future focused work; they are not a mandate for a broad rewrite:

| Module or area | Candidate responsibility to isolate | Suggested protection before change |
|---|---|---|
| `configure_gui.py` | UI state, path presentation, and configuration persistence are still closely coupled. | GUI/config save regression checks and manual launcher verification. |
| `build_neighbors_index.py` | Resume/checkpoint lifecycle and final index-file persistence remain procedural runtime work. | Index-layout regression test plus focused checkpoint tests. |
| `query_contamination_from_index.py` | Target-input parsing and JSON persistence can be separated further from numerical processing. | Query-result schema regression tests. |
| `doctor.py` and `install.py` | Environment diagnostics and installation workflow are intentionally operational but large. | Package-install and source-project diagnostics tests. |

Use this map to select one contained responsibility per release. Strategy or Chain of Responsibility remain unnecessary unless real interchangeable policies emerge.

## Testing strategy

Tests are grouped by intent:

- **Regression tests** (`@pytest.mark.regression`) protect public CLI, pipeline, and result behaviour.
- **Unit tests** (`@pytest.mark.unit`) target pure helpers such as path/config validation, coordinate conversions, ID resolution, and flux calculations.
- **Integration tests** use the bundled example catalogue and targets to verify that the build and query stages work together.
- **Coverage reports** identify untested paths; they guide prioritisation but do not replace behavioural assertions.

Shared temporary inputs belong in `tests/conftest.py`. Configuration lifecycle and process-state boundaries are covered by `tests/test_configuration_lifecycle.py` and `tests/test_runtime_boundaries.py`. Each test is explicitly classified with `@pytest.mark.regression` or `@pytest.mark.unit`; CI uses strict marker handling. Tests should include a docstring when the expected result depends on a scientific rule, a numerical convention, or a non-obvious compatibility behaviour. See [Development workflow](Development.md) and [Public contracts](Public-Contracts.md) for the contributor-facing rules.

## Refactoring guidance

Refactoring should preserve public contracts first. Prefer extracting a focused helper from a large function, adding unit coverage for it, and then simplifying its caller. Do not introduce a design pattern solely for its name: Strategy or Chain of Responsibility should be adopted only when multiple real execution or validation policies need interchangeable implementations.
