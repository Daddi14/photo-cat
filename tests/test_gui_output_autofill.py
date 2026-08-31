# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for type-aware GUI output-path suggestions."""

# These tests call the ConfigGui methods unbound, passing a stand-in for self, so the
# path logic can be exercised without constructing a Tk window. The stand-in is not a
# ConfigGui by type, which is the point of the technique rather than a defect.
# pyright: reportArgumentType=false

from __future__ import annotations

from pathlib import Path

import pytest

from photo_cat.configure_gui import ConfigGui, suggested_result_output


class FakeVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


@pytest.mark.unit
@pytest.mark.parametrize(
    ("role", "selections", "expected_name"),
    [
        ("summary", {"Format": "text"}, "result_summary.txt"),
        ("summary", {"Format": "json"}, "result_summary.json"),
        ("screening", {"Format": "markdown"}, "result_screening.md"),
        ("plot", {"Kind": "sky-map", "Backend": "svg"}, "result_sky-map.svg"),
        ("plot", {"Kind": "flux", "Backend": "matplotlib"}, "result_flux.png"),
        ("plot", {"Kind": "separations", "Format": "pdf", "Backend": "svg"}, "result_separations.pdf"),
        ("publication_plots", {"Format": "pdf"}, "result_publication_plots"),
        ("report", {"Format": "markdown"}, "result_report.md"),
        ("export", {"Format": "parquet"}, "result_export.parquet"),
        ("validation_stats", {}, "result_validation.json"),
        ("validation_residuals", {}, "result_validation_residuals.csv"),
    ],
)
def test_suggested_result_output_uses_role_and_selected_type(
    tmp_path: Path,
    role: str,
    selections: dict[str, str],
    expected_name: str,
) -> None:
    """Every result tool receives a descriptive name and an extension matching its selected type."""
    result_json = tmp_path / "result.json"

    suggestion = suggested_result_output(result_json, role, selections)

    assert Path(suggestion) == tmp_path / expected_name


@pytest.mark.unit
def test_suggested_result_output_avoids_existing_products(tmp_path: Path) -> None:
    """Automatic naming selects a free numbered path instead of targeting an existing product."""
    result_json = tmp_path / "result.json"
    (tmp_path / "result_summary.csv").write_text("existing", encoding="utf-8")

    suggestion = suggested_result_output(result_json, "summary", {"Format": "csv"})

    assert Path(suggestion).name == "result_summary_2.csv"


@pytest.mark.unit
def test_output_refresh_tracks_format_but_preserves_manual_paths(tmp_path: Path) -> None:
    """Format changes update automatic extensions without overwriting a path entered by the user."""
    result_var = FakeVar(str(tmp_path / "result.json"))
    output_var = FakeVar()
    format_var = FakeVar("csv")
    output = {"var": output_var, "last_auto": "", "role": "summary"}
    entry = {
        "var": result_var,
        "outputs": [output],
        "selections": {"Format": format_var},
    }

    ConfigGui.refresh_result_output_entry(None, entry)
    assert output_var.get().endswith("result_summary.csv")

    format_var.set("json")
    ConfigGui.refresh_result_output_entry(None, entry)
    assert output_var.get().endswith("result_summary.json")

    output_var.set(str(tmp_path / "chosen-by-user.custom"))
    format_var.set("text")
    ConfigGui.refresh_result_output_entry(None, entry)
    assert output_var.get().endswith("chosen-by-user.custom")


@pytest.mark.unit
def test_every_result_tool_declares_automatic_outputs() -> None:
    """All GUI tools that receive the pipeline result JSON declare each output they can prefill."""
    specs = [
        ConfigGui.spec_summarize(None),
        ConfigGui.spec_screen(None),
        ConfigGui.spec_plot(None),
        ConfigGui.spec_publication_plots(None),
        ConfigGui.spec_report(None),
        ConfigGui.spec_export(None),
        ConfigGui.spec_validate(None),
    ]

    roles = {
        field["autofill_output"]
        for spec in specs
        for field in spec["fields"]
        if field.get("autofill_output")
    }

    assert roles == {
        "summary",
        "screening",
        "plot",
        "publication_plots",
        "report",
        "export",
        "validation_stats",
        "validation_residuals",
    }
