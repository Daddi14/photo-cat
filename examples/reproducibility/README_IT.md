# Riproduzione dei prodotti PHOTO-CAT per l'articolo

Questa cartella contiene template per rendere riproducibile l'analisi
dell'articolo a partire dagli artefatti software rilasciati. Sostituisci i
percorsi segnaposto di catalogo e target con i file esatti usati nell'articolo
o nel rilascio dati.

Workflow suggerito:

```bash
photo-cat --version
photo-cat build-index --config examples/reproducibility/config_47arcsec.yaml
photo-cat query --config examples/reproducibility/config_47arcsec.yaml
photo-cat build-index --config examples/reproducibility/config_75arcsec.yaml
photo-cat query --config examples/reproducibility/config_75arcsec.yaml
```

Genera quindi i prodotti per l'articolo da ogni JSON dei risultati:

```bash
python examples/reproducibility/reproduce_products.py output/run_47arcsec/results/<result>.json --out-dir output/reproduction/47arcsec
python examples/reproducibility/reproduce_products.py output/run_75arcsec/results/<result>.json --out-dir output/reproduction/75arcsec
```

Genera plot di contaminazione pronti per la pubblicazione per la singola
apertura/risultato che vuoi presentare:

```bash
photo-cat publication-plots output/run_47arcsec/results/<result>.json --aperture-arcsec 47 --output-dir output/publication_plots/47arcsec --format pdf
```

La mappa del cielo usa classi blu/giallo/viola con marker cerchio/triangolo/X e
dimensioni differenti. Le separazioni vengono salvate sia come distribuzione
dei conteggi originale sia come versione normalizzata per area anulare richiesta
dal reviewer.

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
