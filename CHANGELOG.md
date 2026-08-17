# Changelog

All notable changes to PHOTO-CAT are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Releases before 3.0.0 are documented in the
[GitHub releases](https://github.com/Daddi14/photo-cat/releases).

## [Unreleased]

## [3.1.0] - 2026-08-17

### Added

- Photometric band conversion by published Gaia empirical relation, as a second
  method alongside the blackbody conversion. `conversion_method: gaia_empirical`
  evaluates `G - X = sum(c_n * (BP-RP)^n)` directly, so inside its calibrated
  colour range it assumes no spectral shape at all.
- `conversion_method: auto`, which uses the empirical relation where a calibrated
  one exists and the source falls inside its validity range, and falls back to the
  blackbody conversion everywhere else.
- Fifteen published relations predicted by `BP-RP`, each stored with its own
  colour validity range, published scatter, reference and M-giant caveat:
  Johnson-Cousins `johnson_b`, `johnson_v`, `johnson_r`, `cousins_i`; 2MASS
  `2mass_j`, `2mass_h`, `2mass_ks`; SDSS12 `sdss_g`, `sdss_r`, `sdss_i`,
  `sdss_z`; Hipparcos `hipparcos_hp`; Tycho-2 `tycho_bt`, `tycho_vt`.
  Coefficients are transcribed verbatim from the Gaia DR3 documentation
  Sect. 5.5.1, Tables 5.9-5.10 (Riello et al. 2021, A&A 649, A3).
- Short band spellings `b`, `v`, `r`, `i`, `j`, `h`, `ks`, `z`, `hp`, `bt`, `vt`;
  `r` and `i` address the Johnson-Cousins bands, while the SDSS bands keep their
  prefix because a bare `g` would read as Gaia G.
- `colour_used` in target and contaminant result records, so a status such as
  `colour_outside_valid_range` can be checked from the result alone.
- Per-run conversion summary in the query metadata: how many sources each method
  converted, and why the rest were not.
- Conversion statuses `colour_outside_valid_range` and
  `converted_by_fallback_method`.
- GUI note under the conversion-method picker stating which relation will run,
  over what colour range and with what published scatter, and warning when the
  selected band and method cannot be paired.

### Changed

- The output-band picker also lists bands reachable by a published relation, even
  though no transmission curve ships for them.
- `--conversion-method` accepts the new values, and its help text and the
  configuration documentation describe when each method applies.

### Removed

- The `empirical` conversion method, superseded by `gaia_empirical`. It was
  selectable but always raised when used, so no run that previously produced
  results is affected.

## [3.0.0] - 2026-07-30

### Added

- Optional photometric band conversion, estimating contamination in a mission
  band instead of the catalogue band. The colour `BP-RP` gives a
  blackbody-equivalent temperature, the spectrum is integrated through the input
  and output filters, and the anchor band's zero-point is kept so every converted
  magnitude is ratio-safe.
- `photo_cat.photometry` package with pluggable registries for catalogues, SED
  models, and an auto-discovered filter library sharing one filter-file format
  between built-in and user curves.
- Official transmission curves for Gaia G/BP/RP, TESS, CHEOPS, MAUVE and the six
  Ariel channels.
- SVO Filter Profile Service downloader in the GUI, with the facility list
  fetched live so new missions appear without a new tool version.
- `--output-band`, `--conversion-method`, `--conversion-filter-file` and
  `--conversion-catalog` command-line options.
- Result fields `catalog_band`, `output_band`, `conversion_method`,
  `filter_used`, `conversion_status`, `effective_temperature`,
  `converted_target_flux` and the `flux_fraction_*_converted` fractions, with
  per-contaminant `effective_temperature` and `converted_flux`.

### Changed

- Using the conversion requires the catalogue BP and RP bands to be stored in the
  index, so the index must be built with `magnitude_columns` including them.

### Removed

- The empirical colour-polynomial bandpass transformation, replaced by the
  SED-based conversion. **Breaking:** the configuration key
  `query_contamination_from_index.settings.bandpass_transform_file` and the
  `--bandpass-transform-file` option are gone, replaced by the
  `photometric_conversion` block and the `--output-band` family. The result
  fields `bandpass_transform_status`, `bandpass_transform_profile`,
  `bandpass_transformed_band` and the `*_transformed` flux aliases are replaced
  by the conversion fields and the `*_converted` flux fractions.

[Unreleased]: https://github.com/Daddi14/photo-cat/compare/v3.1.0...HEAD
[3.1.0]: https://github.com/Daddi14/photo-cat/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/Daddi14/photo-cat/compare/v2.0.1...v3.0.0
