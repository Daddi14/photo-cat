<!--
SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
SPDX-License-Identifier: GPL-3.0-only
-->

# PHOTO-CAT filter library

Transmission curves used by the photometric band conversion
(`photo_cat.photometry`). The tree is auto-discovered: adding a mission is just
dropping a correctly formatted file in a new folder, with no code change.

## Layout

```
filters/
  <Mission>/<band>.dat
```

- `Gaia/BP.dat` is addressed by the band key `gaia_bp`.
- A single-band mission whose file is named `response.dat` (or `band`, `filter`,
  `throughput`, or the mission name) is also addressed by the mission name alone,
  so `TESS/response.dat` is selectable as `output_band: TESS`.

Band keys are lowercased with non-alphanumeric runs collapsed to `_`.

## File format

Two columns, whitespace- or comma-separated:

```
# unit: angstrom            (optional: nm | angstrom | micron)
# transmission: fraction    (optional: fraction | percent)
wavelength   transmission
3250         3.87e-05
3260         1.76e-04
...
```

- The same format is required for a user-supplied custom filter file
  (`output_band: custom`, `filter_file: path`).
- When the `# unit:` header is absent, the unit is inferred from the wavelength
  magnitude (`<100` micron, `<3000` nm, otherwise angstrom). When the
  `# transmission:` header is absent, values above ~1.5 are treated as a
  percentage. The headers remove any ambiguity; include them when in doubt.

## Shipped curves

| File | Band key | Provenance |
|------|----------|------------|
| `Gaia/G.dat`       | `gaia_g`  | official — SVO `GAIA/GAIA3.G`   |
| `Gaia/BP.dat`      | `gaia_bp` | official — SVO `GAIA/GAIA3.Gbp` |
| `Gaia/RP.dat`      | `gaia_rp` | official — SVO `GAIA/GAIA3.Grp` |
| `TESS/response.dat`   | `tess`      | official — SVO `TESS/TESS.Red`     |
| `CHEOPS/response.dat` | `cheops`    | official — SVO `CHEOPS/CHEOPS.band` |
| `MAUVE/response.dat`  | `mauve`     | official — normalised effective-area curve |
| `Ariel/FGS1.dat`      | `ariel_fgs1`     | official — Ariel FGS1 |
| `Ariel/FGS2.dat`      | `ariel_fgs2`     | official — Ariel FGS2 |
| `Ariel/VISPhot.dat`   | `ariel_visphot`  | official — Ariel VISPhot |
| `Ariel/AIRS-CH0.dat`  | `ariel_airs_ch0` | official — Ariel AIRS-CH0 |
| `Ariel/AIRS-CH1.dat`  | `ariel_airs_ch1` | official — Ariel AIRS-CH1 |
| `Ariel/NIRSpec.dat`   | `ariel_nirspec`  | official — Ariel NIRSpec |

The Gaia, TESS and CHEOPS curves are official responses from the SVO Filter
Profile Service (http://svo2.cab.inta-csic.es/theory/fps/). MAUVE is derived from
its official effective-area curve, normalised to unit peak (only the spectral
shape enters the flux ratio, so the absolute area cancels). The Ariel channels are
official transmission curves. Provenance is recorded in each file header. The Gaia
passbands are also required by the colour-to-temperature engine.

Only official curves are shipped. A file may declare `# provenance:` in its
header; a curve marked `nominal-approximate` (for example a hand-supplied
placeholder) is flagged in the metadata and warned about at runtime, so it is
never mistaken for a measured instrument response.

More filters can be pulled from the SVO Filter Profile Service directly in the
GUI (the "Download a filter from SVO" panel), or programmatically with
`photo_cat.photometry.svo.download_filter`. They are saved into this tree and
become selectable immediately.

## Adding a mission

Download the official transmission curve (for example from the SVO Filter Profile
Service) for the mission band you need, save it in this format under
`filters/<Mission>/<band>.dat`, and it becomes selectable immediately as
`output_band: <mission>` or `<mission>_<band>`. PHOTO-CAT does not ship invented
mission curves; use the published instrument response.
