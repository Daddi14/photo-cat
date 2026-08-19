# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for local PHOENIX interpolation, normalization, and fallback provenance."""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pytest

from photo_cat.photometry.conversion import (
    PHOENIX_PRIMARY_PARAMETERS,
    STATUS_FALLBACK,
    STATUS_VALID,
    convert_magnitudes,
)
from photo_cat.photometry.filters import FilterCurve
from photo_cat.photometry.phoenix import (
    PhoenixGrid,
    PhoenixGridCoverageError,
    PhoenixSpectrum,
    convert_phoenix_photometry,
    synthetic_photometry,
)
from photo_cat import build_neighbors_index, query_contamination_from_index


def _filter(name: str, low: float, high: float) -> FilterCurve:
    wavelength = np.linspace(300.0, 1100.0, 161)
    throughput = ((wavelength >= low) & (wavelength <= high)).astype(np.float64)
    return FilterCurve(name, wavelength, throughput, "test", name, "test")


def _write_grid(root: Path, *, omit: tuple[float, float, float] | None = None) -> Path:
    root.mkdir()
    rows = ["teff,logg,mh,filename,wavelength_unit,flux_kind"]
    wavelength = np.linspace(250.0, 1200.0, 192)
    for teff, logg, mh in itertools.product((3000.0, 4000.0), (4.0, 5.0), (-0.5, 0.0)):
        if (teff, logg, mh) == omit:
            continue
        filename = f"spectra/t{teff:g}_g{logg:g}_m{mh:g}.dat"
        path = root / filename
        path.parent.mkdir(exist_ok=True)
        # Linear dependence on every grid coordinate makes trilinear interpolation
        # analytically exact. Store photon density explicitly for an easy assertion.
        density = (
            1.0
            + wavelength / 1000.0
            + teff / 10000.0
            + logg / 20.0
            + mh / 5.0
        )
        path.write_text(
            "\n".join(f"{wave:.8f} {flux:.12f}" for wave, flux in zip(wavelength, density)),
            encoding="utf-8",
        )
        rows.append(f"{teff},{logg},{mh},{filename},nm,photon")
    (root / "grid_index.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return root


@pytest.mark.unit
def test_phoenix_grid_interpolates_all_three_parameters(tmp_path: Path) -> None:
    """The interpolated spectral shape must respond linearly to Teff, logg, and [M/H]."""
    grid = PhoenixGrid(_write_grid(tmp_path / "grid"))
    spectrum = grid.interpolate(3500.0, 4.5, -0.25)
    expected = 1.0 + spectrum.wavelength_nm / 1000.0 + 0.35 + 4.5 / 20.0 - 0.25 / 5.0
    assert np.allclose(spectrum.photon_flux_density, expected)


@pytest.mark.unit
def test_phoenix_grid_refuses_an_incomplete_local_cell(tmp_path: Path) -> None:
    """Global parameter bounds must not permit interpolation across a missing model corner."""
    grid = PhoenixGrid(_write_grid(tmp_path / "grid", omit=(4000.0, 5.0, 0.0)))
    with pytest.raises(PhoenixGridCoverageError, match="incomplete"):
        grid.interpolate(3500.0, 4.5, -0.25)


@pytest.mark.unit
def test_phoenix_photometry_normalizes_exactly_to_gaia_g(tmp_path: Path) -> None:
    """Using Gaia G as both anchor and target must reproduce the observed magnitude."""
    grid = PhoenixGrid(_write_grid(tmp_path / "grid"))
    gaia = _filter("gaia_g", 500.0, 800.0)
    result = convert_phoenix_photometry(
        grid,
        teff=3500.0,
        logg=4.5,
        mh=-0.25,
        gaia_g_magnitude=12.3,
        gaia_g_filter=gaia,
        target_filter=gaia,
    )
    assert result.target_mag == pytest.approx(12.3)
    assert result.target_flux == pytest.approx(10.0 ** (-0.4 * 12.3))
    assert result.normalization_factor > 0.0


@pytest.mark.unit
def test_synthetic_photometry_uses_the_passband_denominator() -> None:
    """A flat photon spectrum must retain its density regardless of filter width."""
    wavelength = np.linspace(300.0, 1100.0, 161)
    spectrum = PhoenixSpectrum(wavelength, np.full(wavelength.shape, 7.0), np.ones(wavelength.shape))
    assert synthetic_photometry(spectrum, _filter("wide", 350.0, 1000.0)) == pytest.approx(7.0)
    assert synthetic_photometry(spectrum, _filter("narrow", 500.0, 600.0)) == pytest.approx(7.0)


@pytest.mark.unit
def test_optional_extinction_reddens_a_blue_band_after_g_normalization(tmp_path: Path) -> None:
    """A0 extinction must suppress a blue band relative to the Gaia-G anchor."""
    grid = PhoenixGrid(_write_grid(tmp_path / "grid"))
    gaia = _filter("gaia_g", 500.0, 800.0)
    blue = _filter("blue", 330.0, 450.0)
    clear = convert_phoenix_photometry(
        grid,
        teff=3500.0,
        logg=4.5,
        mh=-0.25,
        gaia_g_magnitude=12.0,
        gaia_g_filter=gaia,
        target_filter=blue,
    )
    extincted = convert_phoenix_photometry(
        grid,
        teff=3500.0,
        logg=4.5,
        mh=-0.25,
        gaia_g_magnitude=12.0,
        gaia_g_filter=gaia,
        target_filter=blue,
        azero=1.0,
        apply_extinction=True,
    )
    assert extincted.target_mag > clear.target_mag
    assert extincted.extinction_applied is True


@pytest.mark.unit
def test_phoenix_converter_uses_primary_parameters_then_blackbody_fallback(tmp_path: Path) -> None:
    """Primary Gaia PHOENIX values win, while an incomplete triplet is explicitly delegated."""
    grid_path = _write_grid(tmp_path / "grid")
    result = convert_magnitudes(
        {
            "gaia_g": np.array([12.0, 13.0]),
            "gaia_bp": np.array([12.5, 13.5]),
            "gaia_rp": np.array([11.5, 12.5]),
            "teff_gspphot_phoenix": np.array([3500.0, np.nan]),
            "logg_gspphot_phoenix": np.array([4.5, np.nan]),
            "mh_gspphot_phoenix": np.array([-0.25, np.nan]),
        },
        "gaia_bp",
        "phoenix",
        phoenix_grid_path=str(grid_path),
    )
    assert result.status_codes.tolist() == [STATUS_VALID, STATUS_FALLBACK]
    assert result.diagnostics["sed_model"].tolist() == ["phoenix", "blackbody"]
    assert result.diagnostics["fallback_reason"].tolist() == ["", "missing_phoenix_parameters"]
    assert result.diagnostics["teff_source"][0] == "Gaia_GSPPhot_PHOENIX"
    assert np.isfinite(result.out_magnitudes).all()


@pytest.mark.regression
def test_phoenix_parameters_survive_the_index_and_drive_the_existing_pipeline(tmp_path: Path) -> None:
    """The query consumes PHOENIX magnitudes while contamination stays unchanged."""
    grid_path = _write_grid(tmp_path / "grid")
    catalog_path = tmp_path / "catalog.csv"
    catalog_path.write_text(
        "source_id,ra,dec,phot_g_mean_mag,teff_gspphot_phoenix,"
        "logg_gspphot_phoenix,mh_gspphot_phoenix\n"
        "1,10.000,0.0,10.0,3500,4.5,-0.25\n"
        "2,10.005,0.0,12.0,3500,4.5,-0.25\n",
        encoding="utf-8",
    )
    targets_path = tmp_path / "targets.csv"
    targets_path.write_text("source_id\n1\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
build_neighbors_index:
  io:
    input_catalog: {catalog_path.as_posix()}
    out_dir: {output_dir.as_posix()}
    columns:
      source_id: source_id
      ra: ra
      dec: dec
      phot_g_mean_mag: phot_g_mean_mag
    magnitude_columns:
      gaia_g: phot_g_mean_mag
    stellar_parameter_columns:
      teff_gspphot_phoenix: teff_gspphot_phoenix
      logg_gspphot_phoenix: logg_gspphot_phoenix
      mh_gspphot_phoenix: mh_gspphot_phoenix
  settings:
    use_dask: false
    calculate_separations: false
    max_radius_arcsec: 120
    chunk_size: 2
    buffer_flush_interval: 1
query_contamination_from_index:
  io:
    INDEX_DIR: {output_dir.as_posix()}
    TARGETS_INPUT: {targets_path.as_posix()}
    targets: []
    target_source_id_column: source_id
  settings:
    field_of_view_arcsec: 47
    delta_mag: 5
    contamination_bands: [gaia_g]
    photometric_conversion:
      output_band: tess
      conversion_method: phoenix
      phoenix_grid_path: {grid_path.as_posix()}
      catalog: gaia_dr3
execution:
  run_build: true
  run_query: true
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert build_neighbors_index.main(config_path) == 0
    assert query_contamination_from_index.main(config_path) == 0

    result_path = next((output_dir / "results").glob("*.json"))
    target = json.loads(result_path.read_text(encoding="utf-8"))[0]
    assert target["magnitude_band"] == "tess"
    assert target["conversion_method"] == "phoenix"
    assert target["sed_model"] == "phoenix"
    assert target["teff"] == pytest.approx(3500.0)
    assert target["normalization_factor"] > 0.0
    assert target["fallback_reason"] is None
    assert target["contaminants"][0]["sed_model"] == "phoenix"
    # Equal SED shapes preserve the two-magnitude contrast; the unchanged
    # contamination calculation therefore gives 100 * 10^(-0.4 * 2).
    assert target["flux_fraction_selected"] == pytest.approx(15.85)

    manifest = json.loads((output_dir / "index_manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["stellar_parameters"]) == set(PHOENIX_PRIMARY_PARAMETERS)
