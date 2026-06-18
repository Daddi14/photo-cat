# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Meta-tests for the contributor-facing PHOTO-CAT test conventions."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


TEST_MARKERS = {"unit", "regression"}


def marker_names(function: ast.FunctionDef) -> set[str]:
    """Return the pytest classification markers attached to one test function."""
    names: set[str] = set()

    for decorator in function.decorator_list:
        expression = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (
            isinstance(expression, ast.Attribute)
            and expression.attr in TEST_MARKERS
            and isinstance(expression.value, ast.Attribute)
            and expression.value.attr == "mark"
        ):
            names.add(expression.attr)

    return names


def collect_test_functions(tests_dir: Path) -> list[tuple[Path, ast.FunctionDef]]:
    """Collect top-level test functions from the repository test modules."""
    collected: list[tuple[Path, ast.FunctionDef]] = []

    for path in sorted(tests_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                collected.append((path, node))

    return collected


@pytest.mark.unit
def test_every_test_has_one_explicit_behavioural_or_unit_marker(project_root: Path) -> None:
    """Markers make public contracts distinguishable from replaceable implementation checks."""
    unclassified: list[str] = []
    multiply_classified: list[str] = []

    for path, function in collect_test_functions(project_root / "tests"):
        classifications = marker_names(function)
        label = f"{path.name}::{function.name}"

        if not classifications:
            unclassified.append(label)
        elif len(classifications) > 1:
            multiply_classified.append(label)

    assert not unclassified, "Tests need @pytest.mark.unit or @pytest.mark.regression: " + ", ".join(unclassified)
    assert not multiply_classified, "Tests need exactly one behavioural classification: " + ", ".join(multiply_classified)


@pytest.mark.unit
def test_classified_tests_document_non_obvious_intent(project_root: Path) -> None:
    """Classified tests require docstrings so scientific and compatibility intent survives refactoring."""
    undocumented: list[str] = []

    for path, function in collect_test_functions(project_root / "tests"):
        if marker_names(function) and not ast.get_docstring(function):
            undocumented.append(f"{path.name}::{function.name}")

    assert not undocumented, "Classified tests need concise explanatory docstrings: " + ", ".join(undocumented)
