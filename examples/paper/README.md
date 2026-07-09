# Reproducing paper-style PHOTO-CAT products

This folder contains templates for making the paper analysis reproducible from
released software artifacts. Replace the placeholder catalogue/target paths with
the exact files used for the paper or data release.

Suggested workflow:

```bash
photo-cat --version
photo-cat build-index --config examples/paper/paper_config_47arcsec.yaml
photo-cat query --config examples/paper/paper_config_47arcsec.yaml
photo-cat build-index --config examples/paper/paper_config_75arcsec.yaml
photo-cat query --config examples/paper/paper_config_75arcsec.yaml
```

Then generate paper-style products from each result JSON:

```bash
python examples/paper/reproduce_paper_products.py output/paper_47arcsec/output/<result>.json --out-dir output/paper_products/47arcsec
python examples/paper/reproduce_paper_products.py output/paper_75arcsec/output/<result>.json --out-dir output/paper_products/75arcsec
```

Archive together:

- the exact catalogue-selection query or notebook;
- the exported catalogue and target CSV checksums;
- the config YAML used for each aperture/radius;
- `index_manifest.json`;
- query result JSON files;
- query metadata sidecars under `output/metadata/`;
- generated summaries, SVG plots, and reports.
