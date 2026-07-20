# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Regression tests for publication-oriented contamination plots."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from photo_cat import cli
from photo_cat.publication_plots import (
    SKY_MAP_CLASSES,
    _separation_distribution,
    generate_publication_plots,
)
from photo_cat.result_products import load_result_rows


def write_result(tmp_path: Path) -> Path:
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
def test_sky_map_uses_colourblind_safe_palette() -> None:
    """The sky map must distinguish contamination classes with a colourblind-safe palette."""
    colors = [item["color"] for item in SKY_MAP_CLASSES]
    labels = [item["label"] for item in SKY_MAP_CLASSES]

    assert colors == ["#0072B2", "#E69F00", "#D55E00"]
    assert labels == ["0 contaminants", "1–3 contaminants", ">3 contaminants"]


@pytest.mark.regression
def test_generate_publication_plots_uses_one_configured_aperture(tmp_path: Path) -> None:
    """One result and aperture should produce count, separation, and sky-map plots."""
    result_path = write_result(tmp_path)
    payload = generate_publication_plots(result_path, tmp_path / "plots", aperture_arcsec=47.0, output_format="svg", dpi=72)

    assert payload["settings"]["aperture_arcsec"] == 47.0
    assert payload["plots"]["contaminant_count_distribution"]["aperture_arcsec"] == 47.0
    assert payload["plots"]["contaminant_count_distribution"]["x_scale"] == "linear"
    assert payload["plots"]["contaminant_count_distribution"]["y_scale"] == "log"
    assert payload["plots"]["separation_density_distribution"]["normalization"] == "annular_area_arcsec2"
    assert payload["plots"]["separation_density_distribution"]["aperture_arcsec"] == 47.0
    assert payload["plots"]["contamination_sky_map"]["palette"] == "colourblind_safe"
    assert Path(payload["manifest_path"]).is_file()
    for plot in payload["plots"].values():
        assert Path(plot["path"]).stat().st_size > 0
        assert plot["sha256"]


@pytest.mark.unit
def test_separation_density_divides_by_annular_area_not_bin_width(tmp_path: Path) -> None:
    """A uniform surface density must flatten out once each bin is divided by its ring area.

    Guards the normalization itself: dividing by pi*(r_out^2 - r_in^2) removes the
    geometric bias that makes outer annuli collect more contaminants. Dividing by
    anything proportional to the bin width instead leaves the rising count profile.
    """
    rng = np.random.default_rng(0)
    separations = np.sqrt(rng.uniform(0.0, 47.0**2, size=200_000))
    result_path = tmp_path / "uniform.json"
    result_path.write_text(
        json.dumps([
            {
                "source_id": "uniform",
                "ra": 10.0,
                "dec": -20.0,
                "num_contaminants": int(separations.size),
                "contaminants": [{"source_id": str(i), "sep_arcsec": float(s)} for i, s in enumerate(separations)],
            }
        ]),
        encoding="utf-8",
    )

    rows = load_result_rows(result_path)
    counts, edges = _separation_distribution(rows)
    inside = edges[1:] <= 47.0
    counts, edges = counts[inside], edges[: int(inside.sum()) + 1]
    density = counts / (np.pi * (edges[1:] ** 2 - edges[:-1] ** 2))

    # Flat to within a few percent, and emphatically not rising like the raw counts.
    assert density.std() / density.mean() < 0.1
    assert counts[-1] > 10 * counts[0]


@pytest.mark.regression
def test_cli_publication_plots_generates_public_products(tmp_path: Path) -> None:
    """The public CLI should expose the single-aperture plotting workflow."""
    result_path = write_result(tmp_path)
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
    result_path = write_result(tmp_path)
    with pytest.raises(ValueError, match="format"):
        generate_publication_plots(result_path, tmp_path / "bad", aperture_arcsec=47, output_format="jpg")
    with pytest.raises(ValueError, match="aperture_arcsec"):
        generate_publication_plots(result_path, tmp_path / "bad2", aperture_arcsec=0)
