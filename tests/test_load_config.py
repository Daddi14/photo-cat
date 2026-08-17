# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Tests for configuration parsing, path resolution and validation boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from photo_cat.load_config import (
    GAUSSIAN_FWHM_TO_SIGMA,
    BuildConfig,
    ExecutionConfig,
    QueryConfig,
    load_config,
    resolve_config_path,
)


@pytest.mark.unit
def test_resolve_config_path_prefers_runtime_environment(write_config: Callable[[], Path], monkeypatch: pytest.MonkeyPatch) -> None:
    """A runtime config path must override the repository default without changing the checkout."""
    config_path = write_config()
    monkeypatch.setenv("PHOTO_CAT_CONFIG", str(config_path))

    assert resolve_config_path() == config_path.resolve()


@pytest.mark.unit
def test_load_build_config_resolves_paths(write_config: Callable[[], Path], tmp_path: Path) -> None:
    """Build config converts relative user paths to paths anchored at config.yaml."""
    config = load_config("build_neighbors_index", str(write_config()))

    assert isinstance(config, BuildConfig)
    assert config.input_catalog == str((tmp_path / "catalog.csv").resolve())
    assert config.out_dir == str((tmp_path / "output").resolve())
    assert config.use_dask is False
    assert config.usecolumns == ["source_id", "ra", "dec", "phot_g_mean_mag"]


@pytest.mark.unit
def test_load_query_and_execution_configs(write_config: Callable[[], Path], tmp_path: Path) -> None:
    """Query and execution sections remain separate public configuration contracts."""
    config_path = write_config()
    query = load_config("query_contamination_from_index", str(config_path))
    execution = load_config("execution", str(config_path))

    assert isinstance(query, QueryConfig)
    assert query.INDEX_DIR == str((tmp_path / "output").resolve())
    assert query.TARGETS_INPUT == str((tmp_path / "targets.csv").resolve())
    assert query.field_of_view_arcsec == 47.0
    assert query.delta_mag == 5.0
    # top_hat has no PSF scale, so the influence radius falls back to the aperture.
    assert query.effective_influence_radius_arcsec == 47.0
    assert query.photometric_conversion is None

    assert isinstance(execution, ExecutionConfig)
    assert execution.run_build is True
    assert execution.run_query is True


@pytest.mark.unit
def test_load_config_parses_multiband_and_contamination_model(
    write_config: Callable[..., Path],
    config_text: str,
) -> None:
    """New model settings should be validated while preserving Gaia-G defaults."""
    modified = config_text.replace(
        "      phot_g_mean_mag: phot_g_mean_mag\n  settings:",
        "      phot_g_mean_mag: phot_g_mean_mag\n    magnitude_columns:\n      gaia_bp: phot_bp_mean_mag\n  settings:",
        1,
    ).replace(
        "delta_mag: 5.0",
        "delta_mag: 5.0\n    contamination_bands: [gaia_g, gaia_bp]\n    contamination_model:\n"
        "      mode: gaussian_psf\n      gaussian_fwhm_arcsec: 30\n      influence_sigma: 4",
    )

    build = load_config("build_neighbors_index", str(write_config(modified)), validate_runtime=False)
    query = load_config("query_contamination_from_index", str(write_config(modified)), validate_runtime=False)

    assert isinstance(build, BuildConfig)
    assert build.magnitude_columns["gaia_bp"] == "phot_bp_mean_mag"
    assert isinstance(query, QueryConfig)
    assert query.contamination_bands == ["gaia_g", "gaia_bp"]
    assert query.contamination_model.mode == "gaussian_psf"
    assert query.contamination_model.gaussian_fwhm_arcsec == 30.0
    assert query.contamination_model.influence_sigma == 4.0


@pytest.mark.unit
def test_influence_radius_is_derived_from_the_psf_width_and_sigma_count(
    write_config: Callable[..., Path],
    config_text: str,
) -> None:
    """The outer radius follows the optics: sigma = FWHM / 2.3548, times the sigma count."""
    modified = config_text.replace(
        "delta_mag: 5.0",
        "delta_mag: 5.0\n    contamination_model:\n"
        "      mode: gaussian_psf\n      gaussian_fwhm_arcsec: 2.0\n      influence_sigma: 5.0",
    )

    query = load_config("query_contamination_from_index", str(write_config(modified)), validate_runtime=False)

    assert isinstance(query, QueryConfig)
    assert query.contamination_model.sigma_arcsec == pytest.approx(2.0 / GAUSSIAN_FWHM_TO_SIGMA)
    assert query.effective_influence_radius_arcsec == pytest.approx(5.0 * 2.0 / GAUSSIAN_FWHM_TO_SIGMA)
    # A narrow PSF legitimately stops contributing well inside a wide aperture.
    assert query.effective_influence_radius_arcsec < query.field_of_view_arcsec


@pytest.mark.unit
def test_gaussian_psf_requires_both_fwhm_and_sigma_count(
    write_config: Callable[..., Path],
    config_text: str,
) -> None:
    """A Gaussian PSF without its sigma count has no derivable influence radius."""
    modified = config_text.replace(
        "delta_mag: 5.0",
        "delta_mag: 5.0\n    contamination_model:\n      mode: gaussian_psf\n      gaussian_fwhm_arcsec: 2.0",
    )

    with pytest.raises(ValueError, match="influence_sigma"):
        load_config("query_contamination_from_index", str(write_config(modified)), validate_runtime=False)


@pytest.mark.unit
def test_query_parses_photometric_conversion_and_resolves_custom_filter_path(
    write_config: Callable[..., Path],
    config_text: str,
    tmp_path: Path,
) -> None:
    """The conversion block validates its method and resolves a custom filter path."""
    filter_path = tmp_path / "filters" / "mission.dat"
    modified = config_text.replace(
        "delta_mag: 5.0",
        "delta_mag: 5.0\n    photometric_conversion:\n"
        "      output_band: custom\n      conversion_method: blackbody\n"
        "      filter_file: filters/mission.dat",
    )
    query = load_config("query_contamination_from_index", str(write_config(modified)), validate_runtime=False)

    assert isinstance(query, QueryConfig)
    assert query.photometric_conversion is not None
    assert query.photometric_conversion.output_band == "custom"
    assert query.photometric_conversion.conversion_method == "blackbody"
    assert query.photometric_conversion.filter_file == str(filter_path.resolve())


@pytest.mark.unit
def test_query_accepts_the_empirical_and_auto_conversion_methods(
    write_config: Callable[..., Path],
    config_text: str,
) -> None:
    """Both new methods parse, and a band with a published relation is accepted."""
    for method in ("gaia_empirical", "auto"):
        modified = config_text.replace(
            "delta_mag: 5.0",
            "delta_mag: 5.0\n    photometric_conversion:\n"
            f"      output_band: johnson_v\n      conversion_method: {method}",
        )
        query = load_config("query_contamination_from_index", str(write_config(modified)), validate_runtime=False)

        assert isinstance(query, QueryConfig)
        assert query.photometric_conversion is not None
        assert query.photometric_conversion.conversion_method == method


@pytest.mark.unit
def test_query_rejects_an_empirical_band_without_a_published_relation(
    write_config: Callable[..., Path],
    config_text: str,
) -> None:
    """A mission passband has no Gaia relation, and that fails before the run starts."""
    modified = config_text.replace(
        "delta_mag: 5.0",
        "delta_mag: 5.0\n    photometric_conversion:\n"
        "      output_band: ariel_fgs1\n      conversion_method: gaia_empirical",
    )

    with pytest.raises(ValueError, match="No calibrated Gaia empirical transformation"):
        load_config("query_contamination_from_index", str(write_config(modified)), validate_runtime=False)


@pytest.mark.unit
def test_query_rejects_unknown_conversion_method(
    write_config: Callable[..., Path],
    config_text: str,
) -> None:
    """An unsupported conversion method must fail at parse time with a clear message."""
    modified = config_text.replace(
        "delta_mag: 5.0",
        "delta_mag: 5.0\n    photometric_conversion:\n      output_band: tess\n      conversion_method: magic",
    )
    with pytest.raises(ValueError, match="conversion_method"):
        load_config("query_contamination_from_index", str(write_config(modified)), validate_runtime=False)


@pytest.mark.unit
def test_load_config_rejects_unknown_section(write_config: Callable[[], Path]) -> None:
    """Unknown config sections should fail before a pipeline stage starts."""
    with pytest.raises(ValueError, match="Unknown configuration section"):
        load_config("not_a_real_section", str(write_config()))


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("use_dask: definitely", "use_dask must be true or false"),
        ("max_radius_arcsec: 0", "max_radius_arcsec must be greater than 0.0"),
        ("max_radius_arcsec: 648001", "max_radius_arcsec must be at most 648000.0"),
        ("chunk_size: 0", "chunk_size must be a positive integer"),
        ("field_of_view_arcsec: 0", "field_of_view_arcsec must be greater than 0.0"),
        ("field_of_view_arcsec: 648001", "field_of_view_arcsec must be at most 648000.0"),
    ],
)
@pytest.mark.unit
def test_load_config_rejects_invalid_setting_types_and_ranges(
    write_config: Callable[..., Path],
    config_text: str,
    replacement: str,
    message: str,
) -> None:
    """Malformed numeric and boolean settings fail at config parsing, not during expensive analysis."""
    if (replacement.startswith("field_of_view_arcsec")):
        modified = config_text.replace("field_of_view_arcsec: 47.0", replacement)
        section = "query_contamination_from_index"
    elif (replacement.startswith("use_dask")):
        modified = config_text.replace("use_dask: false", replacement)
        section = "build_neighbors_index"
    elif (replacement.startswith("max_radius_arcsec")):
        modified = config_text.replace("max_radius_arcsec: 120.0", replacement)
        section = "build_neighbors_index"
    else:
        modified = config_text.replace("chunk_size: 2", replacement)
        section = "build_neighbors_index"

    with pytest.raises(ValueError, match=message):
        load_config(section, str(write_config(modified)))
