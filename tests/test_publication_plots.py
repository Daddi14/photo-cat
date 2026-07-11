# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for publication-oriented contamination plots."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from photo_cat import cli
from photo_cat.publication_plots import ACCESSIBLE_SKY_CLASSES, generate_publication_plots


def write_paper_result(tmp_path: Path) -> Path:
    """Create targets spanning every sky-map contamination class."""
    path = tmp_path / "result_47.json"
    path.write_text(
        json.dumps(
            [
                {"source_id": "none", "ra": 10.0, "dec": -20.0, "num_contaminants": 0, "contaminants": []},
                {
                    "source_id": "moderate",
                    "ra": 120.0,
                    "dec": 5.0,
                    "num_contaminants": 2,
                    "contaminants": [
                        {"source_id": "a", "sep_arcsec": 2.4},
                        {"source_id": "b", "sep_arcsec": 20.1},
                    ],
                },
                {
                    "source_id": "crowded",
                    "ra": 280.0,
                    "dec": 45.0,
                    "num_contaminants": 5,
                    "contaminants": [{"source_id": "c", "sep_arcsec": 40.5}],
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.unit
def test_sky_map_encoding_is_not_red_green_and_is_redundant() -> None:
    """The paper map must distinguish classes by colour, shape, and size."""
    colors = [item["color"] for item in ACCESSIBLE_SKY_CLASSES]
    markers = [item["marker"] for item in ACCESSIBLE_SKY_CLASSES]
    sizes = [item["size"] for item in ACCESSIBLE_SKY_CLASSES]

    assert colors == ["#4477AA", "#EECC66", "#AA3377"]
    assert len(set(colors)) == len(ACCESSIBLE_SKY_CLASSES)
    assert len(set(markers)) == len(ACCESSIBLE_SKY_CLASSES)
    assert len(set(sizes)) == len(ACCESSIBLE_SKY_CLASSES)
    assert not {"green", "orange", "red"}.intersection(item["label"].lower() for item in ACCESSIBLE_SKY_CLASSES)


@pytest.mark.regression
def test_generate_publication_plots_uses_one_configured_aperture(tmp_path: Path) -> None:
    """One result and aperture should produce count, separation, density, and sky-map plots."""
    result_path = write_paper_result(tmp_path)
    payload = generate_publication_plots(result_path, tmp_path / "plots", aperture_arcsec=47.0, output_format="svg", dpi=72)

    assert payload["settings"]["aperture_arcsec"] == 47.0
    assert payload["plots"]["contaminant_count_distribution"]["aperture_arcsec"] == 47.0
    assert payload["plots"]["contaminant_count_distribution"]["x_scale"] == "symlog"
    assert payload["plots"]["separation_density_area_normalized"]["normalization"] == "annular_area_arcsec2"
    assert payload["plots"]["contamination_sky_map"]["colour_alone"] is False
    assert Path(payload["manifest_path"]).is_file()
    for plot in payload["plots"].values():
        assert Path(plot["path"]).stat().st_size > 0
        assert plot["sha256"]


@pytest.mark.regression
def test_cli_publication_plots_generates_public_products(tmp_path: Path) -> None:
    """The public CLI should expose the single-aperture manuscript workflow."""
    result_path = write_paper_result(tmp_path)
    output_dir = tmp_path / "cli_figures"

    assert cli.main([
        "publication-plots",
        str(result_path),
        "--aperture-arcsec", "75",
        "--output-dir", str(output_dir),
        "--format", "svg",
        "--dpi", "72",
    ]) == 0
    manifest = json.loads((output_dir / "publication_plots_manifest.json").read_text(encoding="utf-8"))
    assert manifest["settings"]["aperture_arcsec"] == 75.0


@pytest.mark.unit
def test_publication_plots_reject_invalid_settings(tmp_path: Path) -> None:
    """Publication settings should fail clearly before creating misleading figures."""
    result_path = write_paper_result(tmp_path)
    with pytest.raises(ValueError, match="format"):
        generate_publication_plots(result_path, tmp_path / "bad", aperture_arcsec=47, output_format="jpg")
    with pytest.raises(ValueError, match="aperture_arcsec"):
        generate_publication_plots(result_path, tmp_path / "bad2", aperture_arcsec=0)
