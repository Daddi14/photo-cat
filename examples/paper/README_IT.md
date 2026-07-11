# Riproduzione dei prodotti PHOTO-CAT per l'articolo

Questa cartella contiene template per rendere riproducibile l'analisi
dell'articolo a partire dagli artefatti software rilasciati. Sostituisci i
percorsi segnaposto di catalogo e target con i file esatti usati nell'articolo
o nel rilascio dati.

Workflow suggerito:

```bash
photo-cat --version
photo-cat build-index --config examples/paper/paper_config_47arcsec.yaml
photo-cat query --config examples/paper/paper_config_47arcsec.yaml
photo-cat build-index --config examples/paper/paper_config_75arcsec.yaml
photo-cat query --config examples/paper/paper_config_75arcsec.yaml
```

Genera quindi i prodotti per l'articolo da ogni JSON dei risultati:

```bash
python examples/paper/reproduce_paper_products.py output/paper_47arcsec/output/<result>.json --out-dir output/paper_products/47arcsec
python examples/paper/reproduce_paper_products.py output/paper_75arcsec/output/<result>.json --out-dir output/paper_products/75arcsec
```

Archivia insieme:

- la query o il notebook esatto di selezione del catalogo;
- i checksum dei CSV esportati di catalogo e target;
- il file YAML di configurazione per ogni apertura/raggio;
- `index_manifest.json`;
- i JSON dei risultati della query;
- i metadata sidecar della query in `output/metadata/`;
- riassunti, plot SVG e report generati.

`bandpass_transform_example.yaml` documenta lo schema supportato per la
trasformazione empirica da catalogo a banda di missione. I coefficienti sono
segnaposto deliberatamente nulli e non rappresentano una calibrazione Mauve o
di un'altra missione. Prima dell'uso, salva ogni banda richiesta tramite
`build_neighbors_index.io.magnitude_columns`, sostituisci coefficienti e limiti
di validità con valori di calibrazione citati e conserva nei metadata della
query il checksum generato per il profilo.
