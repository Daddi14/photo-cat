# Pipeline e output

PHOTO-CAT ha due fasi principali di pipeline.

## Fase 1: creazione indice dei vicini

La fase di build legge il catalogo, valida le colonne configurate, converte le coordinate e crea un indice delle sorgenti vicine.

I file indice generati vengono scritti nella cartella indice/output configurata.
Gli indici in formato versione 2 includono `index_manifest.json`, che registra
l'impronta del catalogo, il raggio di build, il numero di sorgenti e lo stato di
completamento. Checkpoint e file finali vengono pubblicati in modo atomico.

Gli indici creati con PHOTO-CAT 1.x devono essere ricostruiti. La versione 2 non
carica il precedente formato pickle/object-array. La chiave config obsoleta
`KDTREE_FILENAME` viene ignorata e l'opzione CLI `--kdtree-filename` è stata rimossa.

## Fase 2: query contaminazione

La fase di query carica l’indice e processa i target selezionati.

Per ogni target, PHOTO-CAT identifica le sorgenti vicine dentro il raggio
circolare di query configurato (`field_of_view_arcsec`) e applica i criteri di
magnitudine configurati. La query viene rifiutata se questo raggio supera il
raggio rappresentato dall'indice. Il flusso extra e l'elenco dei contaminanti
usano gli stessi filtri di raggio e magnitudine.

## Modello di contaminazione e terminologia

PHOTO-CAT 2.0.0 produce metriche di contaminazione a livello di catalogo, simili
a un'apertura circolare. È preferibile interpretarlo come strumento di
valutazione del rischio di contaminazione o di screening dei target, salvo che
un'analisi successiva aggiunga modellazione specifica della missione.

- `field_of_view_arcsec` è il raggio angolare circolare usato dalla query per
  selezionare i vicini attorno a ogni target. Nonostante il nome storico della
  chiave di configurazione, non è automaticamente un campo di vista del
  detector, una larghezza di PSF, un'apertura di estrazione o una scala di
  pixel: usa il valore che corrisponde all'apertura di screening che vuoi
  testare.
- Il raggio esterno di ricerca dei vicini è derivato, non configurato: con
  `gaussian_psf` vale `sigma * influence_sigma`, dove
  `sigma = gaussian_fwhm_arcsec / 2.3548`. `top_hat` cerca solo entro l'apertura.
- `delta_mag` è la differenza massima di magnitudine di catalogo ammessa,
  `mag_vicino - mag_target`, perché un vicino venga selezionato.
- Un `contaminant` nell'output JSON è un vicino che supera sia il taglio sul
  raggio circolare configurato sia il taglio `delta_mag`.
- `contamination_model` registra la modalità di pesatura della query. `top_hat`
  è la stima storica non pesata con apertura circolare. `gaussian_psf` applica
  una PSF gaussiana circolare 2D dalla FWHM configurata, per cui il flusso di
  ogni sorgente decade come `exp(-r^2 / 2*sigma^2)` con la distanza angolare dal
  centro dell'apertura, e riporta inoltre metriche di flusso integrate sull'apertura.
- `flux_fraction_selected` viene calcolato sugli stessi contaminanti selezionati
  usati da `num_contaminants`, tramite rapporti di flusso da magnitudini di
  catalogo `10 ** (-0.4 * (mag_vicino - mag_target))`, ed è espresso come
  percentuale del flusso del target.
- `flux_fraction_all_neighbors` usa tutti i vicini validi dentro il raggio
  circolare di query, anche se non superano `delta_mag`.
- `flux_fraction_extra` resta come alias retrocompatibile di
  `flux_fraction_selected`.

Le pesature gaussiane/tabulate opzionali restano modelli radiali circolari, non
simulazioni complete dello strumento. Possono stimare il leakage delle sorgenti
fra apertura e raggio di influenza, ma non modellano PSF asimmetriche o variabili,
pixel del detector, diffrazione o luce diffusa. Un profilo empirico versionato
con polinomio di colore può stimare una magnitudine di missione, ma PHOTO-CAT
non integra una distribuzione spettrale di energia sulla banda strumentale.

## Output JSON

La fase di query scrive un file risultato JSON nella cartella di output configurata.

Ogni risultato target include:

- source ID del target
- coordinate del target
- magnitudine del target, quando disponibile
- frazione di flusso dei contaminanti selezionati
- frazione di flusso di tutti i vicini dentro il raggio
- dizionari opzionali multi-banda per le frazioni di flusso selezionate/tutti i vicini
- metriche opzionali nella banda di missione trasformata, magnitudini di
  target/contaminanti e stato di validità per target
- frazioni di flusso pesate dentro l'apertura, fuori dall'apertura e totali
- conteggi e record delle sorgenti selezionate fuori dall'apertura
- numero di vicini dentro il raggio circolare
- numero di contaminanti selezionati
- lista delle sorgenti contaminanti
- coordinate, magnitudini e separazioni dei contaminanti

Per la riproducibilità, ogni query scrive anche un metadata sidecar JSON in
`INDEX_DIR/results/metadata/`. Il sidecar registra versione di PHOTO-CAT, valori
di configurazione selezionati, numero di target, manifest dell'indice, SHA-256
del catalogo usato nella build e le note sull'ambito del modello riportate sopra.
Il sidecar include anche il checksum del profilo di trasformazione opzionale.
Il JSON dei risultati rimane una lista semplice di target per compatibilità con
gli script esistenti.

Per impostazione predefinita, gli ID target invalidi o assenti dall'indice
vengono saltati con avvisi. Imposta `include_missing_targets: true` o passa
`--include-missing-targets` per conservarli nel JSON come righe con `status`
uguale a `missing_from_index` o `invalid_target_id` e metriche scientifiche
impostate a `null`.

## Riassunti, plot, report e benchmark derivati

Dopo una query, i risultati possono essere convertiti in prodotti riproducibili
adatti anche a un articolo:

```bash
photo-cat summarize INDEX_DIR/results/result.json --format json --output summary.json
photo-cat export INDEX_DIR/results/result.json --format csv --output result.csv
photo-cat plot INDEX_DIR/results/result.json --kind contaminant-counts --output counts.svg
photo-cat plot INDEX_DIR/results/result.json --kind sky-map --backend matplotlib --output sky-map.png
photo-cat plot INDEX_DIR/results/result.json --kind separations-normalized --output separations_area_norm.svg
photo-cat plot INDEX_DIR/results/result.json --kind flux-vs-separation --output flux_vs_separation.svg
photo-cat plot INDEX_DIR/results/result.json --kind sky-map --output sky-map.svg
photo-cat publication-plots INDEX_DIR/results/result.json --aperture-arcsec 47 --output-dir publication_plots
photo-cat report INDEX_DIR/results/result.json --format html --output report.html
photo-cat report INDEX_DIR/results/result.json --format pdf --output report.pdf
photo-cat provenance data/catalog.csv --output catalog_provenance.json
photo-cat benchmark --config config.yaml --output benchmark.json
photo-cat benchmark-table benchmark.json --output benchmark_table.md
photo-cat reproduce --result-json INDEX_DIR/results/result.json --output-dir reproduction
photo-cat merge-bright-stars data/gaia.csv data/bright.csv --output data/merged_catalog.csv
photo-cat screen INDEX_DIR/results/result.json --output screening.csv
photo-cat validate-results INDEX_DIR/results/result.json data/reference.csv --output validation.json --matched-output residuals.csv
```

`summarize` produce conteggi aggregati dei target, conteggi dei contaminanti
selezionati, conteggi di tutti i vicini, statistiche sulle frazioni di flusso e
statistiche sulle separazioni. `plot` scrive SVG senza dipendenze aggiuntive per
conteggi dei contaminanti, frazioni di flusso, separazioni o una semplice mappa
RA/Dec; `--backend matplotlib` abilita output più ricchi da pubblicazione,
incluse separazioni normalizzate per area e scatter plot
flusso-vs-separazione. `export` scrive tabelle target piatte CSV o Parquet.
`report` scrive un documento HTML, Markdown o PDF multipagina con riassunto e plot. `provenance`
registra checksum del catalogo e statistiche di input di base. `benchmark`
esegue le fasi selezionate e registra tempo di esecuzione più picco di
allocazioni Python via `tracemalloc`; se `psutil` è installato campiona anche la
memoria nativa RSS. Una tabella benchmark Markdown o CSV pronta per l'articolo
può essere generata con `benchmark-table`. `reproduce` raccoglie prodotti e checksum in un
manifest di riproduzione per l'articolo. `merge-bright-stars` crea un catalogo
de-duplicato da una tabella in stile Gaia più una tabella supplementare di
stelle brillanti.
`screen` crea una tabella ordinata e motivata di decisioni accept/review/reject.
`validate-results` quantifica l'accordo con una tabella esterna di contaminazione
di missione/riferimento e può esportare i residui abbinati.
`publication-plots` genera dallo stesso risultato a singola apertura la distribuzione
dei conteggi, quella delle separazioni e la mappa del cielo colourblind-safe del
manoscritto. Produce anche la separazione normalizzata per area anulare e salva
checksum di input e output in un manifest.

## Output console

La console della pipeline mostra:

- fase corrente della pipeline
- barre di progresso
- percorso di salvataggio del risultato
- riepilogo finale dei target

Il percorso del JSON salvato è evidenziato nella console, così è più facile trovarlo dopo il completamento dell’esecuzione.
