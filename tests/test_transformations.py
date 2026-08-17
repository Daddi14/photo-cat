# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for the published Gaia empirical colour transformations."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from photo_cat.photometry.conversion import (
    METHOD_AUTO,
    METHOD_GAIA_EMPIRICAL,
    STATUS_NAMES,
    SUPPORTED_CONVERSION_METHODS,
    build_converter,
    convert_magnitudes,
)
from photo_cat.photometry.catalogs import GAIA_DR3
from photo_cat.photometry.transformations import (
    GAIA_EMPIRICAL_TRANSFORMATIONS,
    ColourTransformation,
    find_transformation,
    require_transformation,
    supported_empirical_bands,
)


def _magnitudes(colour: float | list[float], g_mag: float = 12.0) -> dict[str, np.ndarray]:
    """Return aligned Gaia arrays whose BP-RP equals the requested colour(s)."""
    colours = np.atleast_1d(np.asarray(colour, dtype=np.float64))
    anchor = np.full(colours.shape, g_mag, dtype=np.float64)
    return {"gaia_g": anchor, "gaia_bp": anchor + colours, "gaia_rp": anchor}


def _status(result, index: int = 0) -> str:
    return STATUS_NAMES[int(result.status_codes[index])]


@pytest.mark.unit
@pytest.mark.parametrize(
    ("band", "colour", "expected_offset"),
    [
        # Each expected value is the published polynomial for G-X written out by hand,
        # so a typo in a stored coefficient cannot agree with the test by construction.
        ("johnson_v", 0.82, -0.02704 + 0.01424 * 0.82 - 0.2156 * 0.82**2 + 0.01426 * 0.82**3),
        ("cousins_i", 1.5, 0.01753 + 0.76 * 1.5 - 0.0991 * 1.5**2),
        ("2mass_ks", 1.0, -0.0981 + 2.089 * 1.0 - 0.1579 * 1.0**2),
        ("2mass_j", 2.0, 0.01798 + 1.389 * 2.0 - 0.09338 * 2.0**2),
        ("sdss_r", 1.2, -0.09837 + 0.08592 * 1.2 + 0.1907 * 1.2**2 - 0.1701 * 1.2**3 + 0.02263 * 1.2**4),
        ("tycho_bt", 1.0, -0.004288 - 0.8547 + 0.1244 - 0.9085 + 0.4843 - 0.06814),
    ],
)
def test_published_relations_reproduce_their_polynomial(band: str, colour: float, expected_offset: float) -> None:
    """The stored coefficients evaluate to the published G-X offset, so X = G - offset."""
    result = convert_magnitudes(_magnitudes(colour, g_mag=12.0), band, METHOD_GAIA_EMPIRICAL)

    assert result.out_magnitudes[0] == pytest.approx(12.0 - expected_offset, abs=1e-9)
    assert _status(result) == "valid"


@pytest.mark.unit
def test_every_relation_records_its_range_scatter_and_reference() -> None:
    """No relation may be stored without the limits that make it usable."""
    for band, transformation in GAIA_EMPIRICAL_TRANSFORMATIONS.items():
        assert transformation.band == band
        assert transformation.colour_min < transformation.colour_max
        assert transformation.scatter_mag > 0.0
        assert "Riello" in transformation.reference
        assert len(transformation.coefficients) >= 2


@pytest.mark.unit
def test_colour_exactly_on_the_published_bound_is_still_calibrated() -> None:
    """The published bounds are the edge of the calibrated sample, not an open interval."""
    transformation = GAIA_EMPIRICAL_TRANSFORMATIONS["2mass_ks"]
    edges = _magnitudes([transformation.colour_min, transformation.colour_max])

    result = convert_magnitudes(edges, "2mass_ks", METHOD_GAIA_EMPIRICAL)

    assert [_status(result, index) for index in (0, 1)] == ["valid", "valid"]
    assert np.all(np.isfinite(result.out_magnitudes))


@pytest.mark.unit
def test_colour_outside_the_published_range_is_reported_not_extrapolated() -> None:
    """A colour past the calibration edge yields no magnitude and says why."""
    transformation = GAIA_EMPIRICAL_TRANSFORMATIONS["2mass_ks"]
    outside = _magnitudes([transformation.colour_min - 0.01, transformation.colour_max + 0.01])

    result = convert_magnitudes(outside, "2mass_ks", METHOD_GAIA_EMPIRICAL)

    assert [_status(result, index) for index in (0, 1)] == ["colour_outside_valid_range"] * 2
    assert np.all(np.isnan(result.out_magnitudes))
    assert result.summary["converted"] == 0


@pytest.mark.unit
@pytest.mark.parametrize("missing_band", ["gaia_bp", "gaia_rp"])
def test_a_missing_colour_band_leaves_the_source_unconverted(missing_band: str) -> None:
    """Without BP or RP there is no colour, so the relation cannot be applied."""
    magnitudes = _magnitudes([1.0, 1.0])
    magnitudes[missing_band] = magnitudes[missing_band].copy()
    magnitudes[missing_band][1] = np.nan

    result = convert_magnitudes(magnitudes, "johnson_v", METHOD_GAIA_EMPIRICAL)

    assert [_status(result, index) for index in (0, 1)] == ["valid", "missing_input"]
    assert np.isnan(result.out_magnitudes[1])


@pytest.mark.unit
def test_the_empirical_method_reports_no_temperature() -> None:
    """The relation derives no temperature, so none may be reported."""
    result = convert_magnitudes(_magnitudes(1.0), "johnson_v", METHOD_GAIA_EMPIRICAL)

    assert np.all(np.isnan(result.effective_temperature))


@pytest.mark.unit
def test_a_band_without_a_published_relation_is_refused() -> None:
    """Mission passbands have no Gaia relation and must not be matched to a near one."""
    with pytest.raises(ValueError, match="No calibrated Gaia empirical transformation"):
        convert_magnitudes(_magnitudes(1.0), "ariel_fgs1", METHOD_GAIA_EMPIRICAL)

    with pytest.raises(ValueError, match="tess"):
        require_transformation("tess")


@pytest.mark.unit
def test_relations_are_offered_only_for_the_catalogue_they_calibrate() -> None:
    """The relations regress a Gaia colour, so another catalogue must not reuse them."""
    assert find_transformation("johnson_v", "gaia_dr3") is not None
    assert find_transformation("johnson_v", "some_other_survey") is None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("alias", "canonical"),
    [("V", "johnson_v"), ("Ks", "2mass_ks"), ("I", "cousins_i"), ("Hp", "hipparcos_hp")],
)
def test_short_band_spellings_resolve_to_their_system(alias: str, canonical: str) -> None:
    """The classical single-letter names address the system they conventionally mean."""
    transformation = find_transformation(alias)

    assert transformation is not None and transformation.band == canonical


@pytest.mark.unit
def test_auto_falls_back_to_blackbody_when_no_relation_covers_the_band() -> None:
    """A mission passband under auto is simply converted the only way it can be."""
    converter = build_converter(GAIA_DR3, "tess", METHOD_AUTO, None)

    assert converter.method == "blackbody"
    assert converter.output_filter.name == "tess"


@pytest.mark.unit
def test_auto_uses_the_relation_in_range_and_blackbody_outside_it(monkeypatch, tmp_path: Path) -> None:
    """Each source takes whichever method applies to it, and the run records both."""
    # tess is the one shipped band with a transmission curve; giving it a narrow
    # stand-in relation exercises the mixing without inventing a published one.
    stand_in = ColourTransformation(
        band="tess",
        system="Test",
        relation="G-T",
        coefficients=(0.0, -0.5),
        colour_min=0.0,
        colour_max=1.0,
        scatter_mag=0.01,
    )
    monkeypatch.setitem(GAIA_EMPIRICAL_TRANSFORMATIONS, "tess", stand_in)

    magnitudes = _magnitudes([0.5, 2.0, np.nan])
    result = build_converter(GAIA_DR3, "tess", METHOD_AUTO, None).convert(magnitudes)

    assert [_status(result, index) for index in (0, 1, 2)] == [
        "valid",
        "converted_by_fallback_method",
        "missing_input",
    ]
    # In range: the relation, which reports no temperature. Out of range: blackbody.
    assert result.out_magnitudes[0] == pytest.approx(12.0 + 0.5 * 0.5)
    assert np.isnan(result.effective_temperature[0])
    assert np.isfinite(result.effective_temperature[1])
    assert result.summary["method_counts"] == {METHOD_GAIA_EMPIRICAL: 1, "blackbody": 1}
    assert result.summary["fallback_available"] is True


@pytest.mark.unit
def test_auto_without_an_installed_curve_cannot_fall_back_and_says_so() -> None:
    """No transmission curve means no blackbody fallback; that is reported, not faked."""
    transformation = GAIA_EMPIRICAL_TRANSFORMATIONS["2mass_ks"]
    magnitudes = _magnitudes([1.0, transformation.colour_max + 1.0])

    result = build_converter(GAIA_DR3, "2mass_ks", METHOD_AUTO, None).convert(magnitudes)

    assert [_status(result, index) for index in (0, 1)] == ["valid", "colour_outside_valid_range"]
    assert result.summary["fallback_available"] is False


@pytest.mark.unit
def test_conversion_is_independent_of_source_order() -> None:
    """Every source is converted from its own photometry alone."""
    colours = [0.3, 1.4, 2.2, 0.9]
    forward = convert_magnitudes(_magnitudes(colours), "johnson_v", METHOD_GAIA_EMPIRICAL)
    reversed_result = convert_magnitudes(_magnitudes(colours[::-1]), "johnson_v", METHOD_GAIA_EMPIRICAL)

    assert forward.out_magnitudes == pytest.approx(reversed_result.out_magnitudes[::-1])


@pytest.mark.unit
def test_the_selectable_methods_cover_both_families() -> None:
    """Both conversion families and the combined mode stay selectable."""
    assert set(SUPPORTED_CONVERSION_METHODS) == {"blackbody", "phoenix", METHOD_GAIA_EMPIRICAL, METHOD_AUTO}
    assert supported_empirical_bands() == sorted(GAIA_EMPIRICAL_TRANSFORMATIONS)


@pytest.mark.unit
def test_the_picker_offers_bands_that_have_a_relation_but_no_filter_file() -> None:
    """A band is selectable when either a curve or a published relation can reach it."""
    from photo_cat.configure_gui import conversion_output_band_values
    from photo_cat.photometry.library import library_filter_path

    values = conversion_output_band_values()

    assert "tess" in values and "custom" in values
    assert "johnson_v" in values and library_filter_path("johnson_v") is None
    assert len(values) == len(set(values))


@pytest.mark.unit
@pytest.mark.parametrize(
    ("band", "method", "expected_fragment", "warns"),
    [
        ("johnson_v", METHOD_GAIA_EMPIRICAL, "G-V (Johnson-Cousins)", False),
        ("ariel_fgs1", METHOD_GAIA_EMPIRICAL, "No calibrated Gaia empirical transformation", True),
        ("ariel_fgs1", METHOD_AUTO, "no published Gaia relation", False),
        # A relation with no installed curve: auto has nothing to fall back to.
        ("2mass_ks", METHOD_AUTO, "no fallback is possible", True),
        ("tess", "blackbody", "", False),
    ],
)
def test_the_gui_states_which_relation_will_run(band: str, method: str, expected_fragment: str, warns: bool) -> None:
    """An unsupported band-and-method pairing is visible before the run, not after."""
    from photo_cat.configure_gui import conversion_method_note

    text, warning = conversion_method_note(band, method, "gaia_dr3")

    assert expected_fragment in text
    assert warning is warns


@pytest.mark.unit
def test_metadata_records_the_relation_that_was_applied() -> None:
    """A result must be reproducible from its own metadata."""
    result = convert_magnitudes(_magnitudes(1.0), "johnson_v", METHOD_GAIA_EMPIRICAL)
    relation = result.metadata["transformation"]

    assert relation["relation"] == "G-V"
    assert relation["colour_name"] == "G_BP-G_RP"
    assert relation["coefficients"] == list(GAIA_EMPIRICAL_TRANSFORMATIONS["johnson_v"].coefficients)
    assert relation["scatter_mag"] == pytest.approx(0.03017)
    assert result.metadata["filter_used"] is None
