# Reproducing PHOTO-CAT products

This folder contains templates for making the analysis reproducible from
released software artifacts. Replace the placeholder catalogue/target paths with
the exact files used for the analysis or data release.

Suggested workflow:

```bash
photo-cat --version
photo-cat build-index --config examples/reproducibility/config_47arcsec.yaml
photo-cat query --config examples/reproducibility/config_47arcsec.yaml
photo-cat build-index --config examples/reproducibility/config_75arcsec.yaml
photo-cat query --config examples/reproducibility/config_75arcsec.yaml
```

Then generate reproducible products from each result JSON:

```bash
python examples/reproducibility/reproduce_products.py output/run_47arcsec/results/<result>.json --out-dir output/reproduction/47arcsec
python examples/reproducibility/reproduce_products.py output/run_75arcsec/results/<result>.json --out-dir output/reproduction/75arcsec
```

Generate publication-ready contamination plots for whichever single
aperture/result is being presented:

```bash
photo-cat publication-plots output/run_47arcsec/results/<result>.json --aperture-arcsec 47 --output-dir output/publication_plots/47arcsec --format pdf
```

The sky map uses blue/yellow/purple classes plus circle/triangle/X markers and
different sizes. Separations are written both as the original count
distribution and as an annular-area-normalized reviewer-facing companion.

Archive together:

- the exact catalogue-selection query or notebook;
- the exported catalogue and target CSV checksums;
- the config YAML used for each aperture/radius;
- `index_manifest.json`;
- query result JSON files;
- query metadata sidecars under `output/metadata/`;
- generated summaries, SVG plots, and reports.

The photometric band conversion estimates contamination in a mission band from
catalogue colours. Store the BP and RP bands through
`build_neighbors_index.io.magnitude_columns`, then set
`query_contamination_from_index.settings.photometric_conversion` with an
`output_band` (a built-in filter such as `tess`, or `custom` with a
`filter_file`). Gaia, TESS, CHEOPS and MAUVE ship as official curves. See
`docs/Configuration.md` for the full description.
