# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for the mission-agnostic photometric band conversion."""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pytest

from photo_cat.photometry.catalogs import GAIA_DR3, resolve_catalog
from photo_cat.photometry.conversion import build_converter, convert_magnitudes
from photo_cat.photometry.filters import load_filter
from photo_cat.photometry.library import (
    FILTERS_ROOT,
    USER_FILTERS_DIR_ENV,
    available_output_bands,
    library_filter_path,
    load_library_filter,
    user_filters_root,
)
from photo_cat.photometry.sed import blackbody_photon_density


def _write_filter(path: Path, lo: float, hi: float, header: str = "# unit: nm\n# transmission: fraction\n") -> Path:
    """Write a synthetic top-hat filter spanning [lo, hi] nanometres."""
    wavelength = np.linspace(lo - 20, hi + 20, 80)
    throughput = ((wavelength >= lo) & (wavelength <= hi)).astype(float)
    path.write_text(header + "\n".join(f"{w} {t}" for w, t in zip(wavelength, throughput)))
    return path


@pytest.mark.unit
def test_blackbody_peaks_bluer_when_hotter() -> None:
    """A hotter blackbody must put relatively more photon flux at short wavelengths."""
    wavelength = np.linspace(300.0, 1000.0, 400)
    hot = blackbody_photon_density(wavelength, 12000.0)
    cool = blackbody_photon_density(wavelength, 3000.0)
    blue_share_hot = hot[wavelength < 500].sum() / hot.sum()
    blue_share_cool = cool[wavelength < 500].sum() / cool.sum()
    assert blue_share_hot > blue_share_cool
    assert np.all(np.isfinite(hot)) and np.all(hot >= 0.0)


@pytest.mark.unit
def test_filter_unit_and_percent_normalisation(tmp_path: Path) -> None:
    """Angstrom wavelengths and percentage transmission normalise to nm and a fraction."""
    path = tmp_path / "f.dat"
    path.write_text("# unit: angstrom\n# transmission: percent\n5000 50\n6000 100\n7000 50\n")
    curve = load_filter(path)
    assert curve.wavelength_nm.tolist() == [500.0, 600.0, 700.0]
    assert curve.throughput.max() == pytest.approx(1.0)
    assert curve.throughput.min() == pytest.approx(0.5)


@pytest.mark.unit
def test_filter_autodetects_units_without_headers(tmp_path: Path) -> None:
    """Missing headers fall back to magnitude heuristics: angstrom-scale and percent."""
    path = tmp_path / "f.dat"
    path.write_text("5000 40\n6000 80\n7000 40\n")
    curve = load_filter(path)
    assert curve.wavelength_nm[0] == pytest.approx(500.0)  # 5000 A -> 500 nm
    assert curve.throughput.max() == pytest.approx(0.8)  # 80 read as percent -> 0.80


@pytest.mark.unit
def test_filter_rejects_single_column(tmp_path: Path) -> None:
    """A one-column file cannot define a transmission curve."""
    path = tmp_path / "bad.dat"
    path.write_text("# unit: nm\n500\n600\n")
    with pytest.raises(ValueError, match="two columns"):
        load_filter(path)


@pytest.mark.unit
def test_gaia_to_gaia_conversion_is_identity() -> None:
    """Converting the anchor band to itself must return the anchor magnitudes exactly."""
    mags = {
        "gaia_g": np.array([12.0, 15.5, 9.0]),
        "gaia_bp": np.array([12.4, 16.2, 9.1]),
        "gaia_rp": np.array([11.6, 14.6, 8.8]),
    }
    result = convert_magnitudes(mags, "gaia_g", "blackbody")
    assert np.allclose(result.out_magnitudes, mags["gaia_g"])


@pytest.mark.unit
def test_identity_conversion_skips_the_flux_ratio() -> None:
    """The anchor-equals-output case is flagged so the ratio work can be skipped."""
    converter = build_converter(GAIA_DR3, "gaia_g", "blackbody", None)
    assert converter.is_identity is True
    other = build_converter(GAIA_DR3, "gaia_rp", "blackbody", None)
    assert other.is_identity is False


@pytest.mark.unit
def test_solar_colour_maps_to_solar_temperature() -> None:
    """The colour zero-point anchor places BP-RP 0.82 at 5772 K."""
    mags = {"gaia_g": np.array([10.0]), "gaia_bp": np.array([10.41]), "gaia_rp": np.array([9.59])}
    result = convert_magnitudes(mags, "gaia_rp", "blackbody")
    assert result.effective_temperature[0] == pytest.approx(5772.0, abs=5.0)


@pytest.mark.unit
def test_bluer_source_is_hotter_and_brighter_in_a_blue_band() -> None:
    """Equal-G blue and red stars diverge once converted into a blue output band."""
    mags = {
        "gaia_g": np.array([13.0, 13.0]),
        "gaia_bp": np.array([12.9, 14.0]),   # BP-RP = -0.4 (blue) and 2.0 (red)
        "gaia_rp": np.array([13.3, 12.0]),
    }
    result = convert_magnitudes(mags, "gaia_bp", "blackbody")
    assert result.effective_temperature[0] > result.effective_temperature[1]
    # Brighter means a smaller magnitude: the blue star wins in the blue band.
    assert result.out_magnitudes[0] < result.out_magnitudes[1]


@pytest.mark.unit
def test_conversion_requires_the_catalogue_colour_bands() -> None:
    """A clear error names the missing colour bands rather than failing obscurely."""
    with pytest.raises(ValueError, match="gaia_bp|gaia_rp"):
        convert_magnitudes({"gaia_g": np.array([12.0])}, "gaia_rp", "blackbody")


@pytest.mark.unit
def test_missing_input_is_flagged_and_not_converted() -> None:
    """Non-finite catalogue magnitudes yield NaN output and a missing-input status."""
    mags = {
        "gaia_g": np.array([12.0, np.nan]),
        "gaia_bp": np.array([12.4, 12.0]),
        "gaia_rp": np.array([11.6, np.nan]),
    }
    result = convert_magnitudes(mags, "gaia_rp", "blackbody")
    assert np.isfinite(result.out_magnitudes[0])
    assert np.isnan(result.out_magnitudes[1])
    assert result.status_codes.tolist() == [1, 0]


@pytest.mark.unit
def test_custom_output_band_requires_a_filter_file(tmp_path: Path) -> None:
    """The custom band cannot be resolved without its transmission file."""
    with pytest.raises(ValueError, match="custom"):
        build_converter(GAIA_DR3, "custom", "blackbody", None)

    custom = _write_filter(tmp_path / "mine.dat", 600.0, 700.0)
    converter = build_converter(GAIA_DR3, "custom", "blackbody", str(custom))
    assert converter.output_filter is not None
    assert converter.output_filter.name == "custom"


@pytest.mark.unit
def test_phoenix_is_selectable_but_unavailable() -> None:
    """An unimplemented SED model is accepted for selection but fails with guidance."""
    with pytest.raises(ValueError, match="phoenix"):
        convert_magnitudes(
            {"gaia_g": np.array([12.0]), "gaia_bp": np.array([12.4]), "gaia_rp": np.array([11.6])},
            "gaia_rp",
            "phoenix",
        )


@pytest.mark.unit
def test_an_unknown_conversion_method_lists_the_supported_ones() -> None:
    """A misspelled method names its alternatives instead of failing obscurely."""
    with pytest.raises(ValueError, match="gaia_empirical"):
        convert_magnitudes(
            {"gaia_g": np.array([12.0]), "gaia_bp": np.array([12.4]), "gaia_rp": np.array([11.6])},
            "gaia_rp",
            "not_a_method",
        )


@pytest.mark.regression
def test_built_in_library_ships_only_official_missions() -> None:
    """The shipped library holds Gaia plus the official mission curves, no placeholders."""
    bands = set(available_output_bands())
    assert {"gaia_g", "gaia_bp", "gaia_rp", "tess", "cheops", "mauve"} <= bands
    for band in bands:
        assert load_library_filter(band).is_nominal is False


@pytest.mark.unit
def test_the_user_library_lives_outside_the_installed_package(monkeypatch: pytest.MonkeyPatch) -> None:
    """Downloaded filters must survive reinstalling or upgrading the package."""
    monkeypatch.delenv(USER_FILTERS_DIR_ENV, raising=False)
    root = user_filters_root()

    assert (root.name, root.parent.name) == ("filters", "photo-cat")
    assert not root.is_relative_to(FILTERS_ROOT)


@pytest.mark.regression
def test_a_filter_added_to_the_user_library_is_discovered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A curve outside the package is addressable exactly like a shipped one."""
    monkeypatch.setenv(USER_FILTERS_DIR_ENV, str(tmp_path))
    (tmp_path / "MyMission").mkdir()
    _write_filter(tmp_path / "MyMission" / "response.dat", 600.0, 700.0)

    assert "mymission" in available_output_bands()
    assert load_library_filter("mymission").throughput.max() == pytest.approx(1.0)


@pytest.mark.regression
def test_shipped_filters_stay_available_alongside_the_user_library(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The package remains a search root, so a filter left there keeps resolving."""
    monkeypatch.setenv(USER_FILTERS_DIR_ENV, str(tmp_path / "empty"))
    path = library_filter_path("tess")

    assert path is not None and Path(path).is_relative_to(FILTERS_ROOT)


@pytest.mark.regression
def test_a_user_curve_takes_precedence_over_a_shipped_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Installing a curve locally is how a shipped one is replaced without editing it."""
    monkeypatch.setenv(USER_FILTERS_DIR_ENV, str(tmp_path))
    (tmp_path / "TESS").mkdir()
    _write_filter(tmp_path / "TESS" / "response.dat", 600.0, 700.0)

    path = library_filter_path("tess")

    assert path is not None and Path(path).is_relative_to(tmp_path)


@pytest.mark.regression
def test_an_unconverted_target_reports_unknown_contamination_not_zero() -> None:
    """A target with no reference magnitude must not read as a clean target.

    Its flux ratios are undefined, and 0.0 is the value a measured, uncontaminated
    target would carry. For a screening tool the two must not look the same.
    """
    from photo_cat.query_contamination_from_index import flux_fraction_by_band

    magnitudes = {
        "gaia_g": np.array([10.0, 12.0]),
        "converted_band": np.array([np.nan, 11.0]),
    }

    metrics = flux_fraction_by_band(
        0, np.array([1]), np.array([True]), magnitudes, np.array([1.0])
    )

    # The catalogue band is still measured for this target, so it stays a number.
    catalogue_metric = metrics["gaia_g"]
    assert catalogue_metric is not None and catalogue_metric > 0.0
    assert metrics["converted_band"] is None


@pytest.mark.regression
def test_nominal_custom_filter_warns_at_build_time(tmp_path: Path) -> None:
    """A user filter declaring nominal provenance must raise a visible warning."""
    nominal = tmp_path / "nominal.dat"
    nominal.write_text("# provenance: nominal-approximate\n# unit: nm\n600 0\n650 1\n700 0\n")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        build_converter(resolve_catalog("gaia_dr3"), "custom", "blackbody", str(nominal))
    assert any("NOMINAL" in str(w.message) for w in caught)
