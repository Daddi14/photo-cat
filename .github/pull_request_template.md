# Pull request

## Summary

Describe the change, why it is needed, and any public contract affected.

## Type of change

- [ ] Bug fix
- [ ] Feature
- [ ] Documentation
- [ ] Maintenance/refactor

## Public behaviour and compatibility

- [ ] I reviewed `docs/Public-Contracts.md` when changing CLI, configuration, index, query output, diagnostics, or launchers.
- [ ] I documented any intentional compatibility impact or migration step.

## Tests and local verification

- [ ] I added or updated relevant unit and/or regression tests.
- [ ] I ran `pytest`.
- [ ] I ran `pytest --cov=photo_cat --cov-report=term-missing` for a substantial code change.
- [ ] I ran relevant CLI, pipeline, or sample-workflow checks.
- [ ] I added a concise docstring to any non-trivial new test.

## Repository checks

- [ ] I did not commit generated files such as `.venv/`, `.runtime/`, logs, outputs, `__pycache__/`, or `*.pyc`.
- [ ] I updated English and Italian documentation where user-facing behaviour changed.
- [ ] I preserved GPL-3.0-only licensing and SPDX/REUSE metadata.
- [ ] I ran `git diff --check`.

## Notes for reviewers

Add testing notes, limitations, public-contract impact, or follow-up work.
