# Uso da riga di comando

PHOTO-CAT può essere eseguito da riga di comando con un file YAML di configurazione e override diretti opzionali.

La GUI resta il punto di ingresso consigliato per l’uso desktop normale. La CLI è pensata per esecuzioni da script, sistemi remoti, cluster, pipeline riproducibili e workflow batch.

## Lingua

Usa l'opzione globale `--language` prima del comando per selezionare guida e messaggi in inglese o italiano:

```bash
photo-cat --language it --help
photo-cat --language it doctor
photo-cat --language it run --config config.yaml
```

L'opzione esplicita ha la precedenza. In sua assenza PHOTO-CAT usa `PHOTO_CAT_LANGUAGE`, poi `interface.language` della configurazione selezionata e infine l'inglese. Nomi dei comandi, nomi delle opzioni, chiavi degli schemi leggibili da macchina ed etichette scientifiche dei grafici restano stabili e in inglese.

## Comandi base

```bash
photo-cat --help
photo-cat configure
photo-cat run --config config.yaml
photo-cat build-index --config config.yaml
photo-cat query --config config.yaml
photo-cat summarize output/index/results/result.json
photo-cat export output/index/results/result.json --format csv --output output/result.csv
photo-cat plot output/index/results/result.json --kind contaminant-counts
photo-cat publication-plots output/index/results/result.json --aperture-arcsec 47 --output-dir output/publication_plots
photo-cat report output/index/results/result.json --format html
photo-cat screen output/index/results/result.json --output output/screening.csv
photo-cat validate-results output/index/results/result.json data/reference.csv --output output/validation.json
photo-cat benchmark --config config.yaml --output output/benchmark.json
photo-cat benchmark-table output/benchmark.json --output output/benchmark_table.md
photo-cat provenance data/catalog.csv --output output/catalog_provenance.json
photo-cat reproduce --config examples/reproducibility/config_47arcsec.yaml --output-dir output/reproduction
photo-cat merge-bright-stars data/gaia.csv data/bright.csv --output data/merged_catalog.csv
photo-cat doctor
```

`screen` (alias `rank`) ordina i target in base a una metrica di contaminazione
e assegna `accept`, `review` o `reject` con soglie percentuali esplicite.
`validate-results` (alias `validate`) unisce per source ID un CSV esterno di
contaminazione di riferimento e calcola bias, residuo mediano, MAE, RMSE e,
opzionalmente, accuratezza rispetto a una soglia.

`publication-plots` genera un insieme coordinato di plot da pubblicazione da un
singolo JSON e dall'apertura rappresentata da quel risultato. Scrive:

- distribuzione dei conteggi dei contaminanti, con Y logaritmico e X
  simmetrico-log che conserva lo zero;
- distribuzione grezza delle separazioni e versione aggiuntiva
  normalizzata per area anulare;
- mappa RA/Dec blu/giallo/viola con marker distinti
  cerchio/triangolo/X e dimensioni differenti, senza affidarsi al solo colore;
- un `publication_plots_manifest.json` con checksum.

Sono supportati output PNG, PDF e SVG tramite `--format`.

Quando è stato usato un profilo di banda, esegui screening o validazione della
stima di missione con `--metric flux_fraction_total_weighted_transformed`.

## Diagnostica doctor per l'automazione

Per impostazione predefinita `photo-cat doctor` stampa un report leggibile:

```bash
photo-cat doctor
```

Per l'automazione può produrre un singolo documento JSON leggibile da macchina:

```bash
photo-cat doctor --format json
```

Il report JSON usa la versione di schema `1` e contiene i seguenti campi di primo livello stabili:

```json
{
  "schema_version": 1,
  "ok": true,
  "checks": [
    {
      "name": "python",
      "status": "pass",
      "message": "Python",
      "detail": "3.13.0"
    }
  ],
  "summary": {
    "passed": 1,
    "warnings": 0,
    "failed": 0,
    "information": 0
  }
}
```

`status` può essere `pass`, `warn`, `fail` oppure `info`. Il comando restituisce `0` quando nessun controllo fallisce e `1` quando uno o più controlli falliscono. Gli avvisi restano visibili nel JSON ma non cambiano uno stato di uscita riuscito. Il formato predefinito `text` resta invariato per l'uso interattivo.

## Modello di configurazione

Il comando standard legge i valori da `config.yaml`:

```bash
photo-cat run --config config.yaml
```

Gli override CLI possono sostituire qualsiasi valore del file YAML solo per quell’esecuzione:

```bash
photo-cat run --config config.yaml --delta-mag 4.0 --field-of-view-arcsec 60.0
```

Gli override non modificano permanentemente `config.yaml`. PHOTO-CAT scrive una configurazione temporanea di runtime, esegue il comando richiesto e rimuove il file temporaneo alla fine.

## Ricetta per run riproducibili

Per analisi che devono essere riviste o rieseguite, salva i comandi esatti e
gli input usati per creare il CSV catalogo e gli output PHOTO-CAT. Una sequenza
minima di comandi è:

```bash
photo-cat --version
photo-cat build-index --config config.yaml --input-catalog data/my_catalog.csv --out-dir output/my_index --max-radius-arcsec 120
photo-cat query --config config.yaml --index-dir output/my_index --targets-input data/my_targets.csv --field-of-view-arcsec 47 --delta-mag 5
photo-cat query --config config.yaml --bandpass-transform-file examples/reproducibility/bandpass_transform_example.yaml
```

La build scrive `index_manifest.json` con SHA-256 del catalogo e impostazioni
che definiscono l'indice dei vicini. La query scrive il JSON dei risultati più
un metadata sidecar in `output/my_index/output/metadata/` con versione di
PHOTO-CAT, impostazioni della query, manifest dell'indice, numero di target
processati e note sull'ambito del modello. Conserva questi file insieme alla
query di selezione del catalogo o al notebook che ha generato
`data/my_catalog.csv`.

## Riassunti, export, plot, report, provenance e benchmark

Riassumi un risultato di query:

```bash
photo-cat summarize output/my_index/results/result.json
photo-cat summarize output/my_index/results/result.json --format json --output output/summary.json
photo-cat summarize output/my_index/results/result.json --format csv --output output/summary.csv
```

Crea plot SVG senza dipendenze opzionali:

```bash
photo-cat plot output/my_index/results/result.json --kind contaminant-counts --output output/counts.svg
photo-cat plot output/my_index/results/result.json --kind flux --output output/flux.svg
photo-cat plot output/my_index/results/result.json --kind separations --output output/separations.svg
photo-cat plot output/my_index/results/result.json --kind separations-normalized --output output/separations_area_norm.svg
photo-cat plot output/my_index/results/result.json --kind flux-vs-separation --output output/flux_vs_separation.svg
photo-cat plot output/my_index/results/result.json --kind contamination-vs-magnitude --output output/contamination_vs_magnitude.svg
photo-cat plot output/my_index/results/result.json --kind sky-map --output output/sky-map.svg
photo-cat plot output/my_index/results/result.json --kind sky-map --backend matplotlib --output output/sky-map.png
```

Esporta tabelle target piatte:

```bash
photo-cat export output/my_index/results/result.json --format csv --output output/result.csv
photo-cat export output/my_index/results/result.json --format parquet --output output/result.parquet
```

Crea un report compatto:

```bash
photo-cat report output/my_index/results/result.json --format html --output output/report.html
photo-cat report output/my_index/results/result.json --format markdown --output output/report.md
```

Registra metadata di benchmark:

```bash
photo-cat benchmark --config config.yaml --output output/benchmark.json
photo-cat benchmark --config config.yaml --no-run-build --run-query --output output/query_benchmark.json
```

Il JSON di benchmark include versione PHOTO-CAT, metadata Python/piattaforma,
durate delle fasi selezionate, codici di stato e picco di allocazioni Python via
`tracemalloc`. Il contatore delle allocazioni è riproducibile e senza dipendenze.
Se `psutil` è installato, il benchmark campiona anche la memoria nativa RSS;
altrimenti i campi RSS sono presenti ma segnati come non disponibili.

Cattura provenance del catalogo:

```bash
photo-cat provenance data/my_catalog.csv --adql-file examples/reproducibility/gaia_dr3_g17_selection.adql --output output/catalog_provenance.json
```

Il JSON di provenance include percorso del catalogo, SHA-256, dimensione in byte,
numero di righe, colonne, conteggi nulli, range numerici per RA/Dec/magnitudine,
conteggio dei source ID duplicati e checksum opzionale del file ADQL/query.

Genera prodotti per articolo/revisione da risultati esistenti o configurazioni riproducibili:

```bash
photo-cat reproduce --result-json output/my_index/results/result.json --output-dir output/reproduction
photo-cat reproduce --config examples/reproducibility/config_47arcsec.yaml --config examples/reproducibility/config_75arcsec.yaml --output-dir output/reproduction
photo-cat reproduce --config config.yaml --run-configs --output-dir output/reproduction
```

Il comando copia configurazioni/risultati, scrive riassunti, plot, report HTML e
`paper_reproduction_manifest.json` con checksum.

Unisci un CSV supplementare di stelle brillanti a un catalogo in stile Gaia prima
di creare l'indice:

```bash
photo-cat merge-bright-stars data/gaia.csv data/bright_stars.csv --output data/merged_catalog.csv --provenance-output output/merge_provenance.json
```

Gli ID sorgente duplicati vengono de-duplicati con `--prefer bright` per impostazione predefinita.

## Gestione dei percorsi

I percorsi passati tramite override CLI sono risolti rispetto alla cartella da cui viene eseguito il comando.

Esempio:

```bash
photo-cat run --config configs/run.yaml --input-catalog data/catalog.csv
```

`data/catalog.csv` viene risolto a partire dalla cartella corrente del terminale.

## Errori di input e output

I comandi CLI restituiscono uno stato diverso da zero e stampano un messaggio `ERROR:` su standard error quando un file di configurazione, catalogo, CSV dei target, cartella indice o percorso di output non è valido.

Esempi:

```bash
photo-cat build-index --config missing.yaml
photo-cat build-index --config config.yaml --input-catalog data/missing_catalog.csv
```

`out_dir` deve essere una cartella e non può coincidere con un file esistente.

Per `photo-cat query`, la cartella indice deve contenere i file dell'indice completato. Il risultato viene creato in `INDEX_DIR/results`; un file chiamato `results` viene segnalato come errore e non viene sovrascritto.

## Pipeline completa con override diretti

```bash
photo-cat run ^
  --config config.yaml ^
  --input-catalog data/my_catalog.csv ^
  --targets-input data/my_targets.csv ^
  --out-dir output/my_run ^
  --index-dir output/my_run ^
  --catalog-source-id-column source_id ^
  --ra-column ra ^
  --dec-column dec ^
  --mag-column phot_g_mean_mag ^
  --magnitude-columns gaia_g=phot_g_mean_mag,gaia_bp=phot_bp_mean_mag,gaia_rp=phot_rp_mean_mag ^
  --max-radius-arcsec 120 ^
  --field-of-view-arcsec 47 ^
  --delta-mag 5 ^
  --contamination-bands gaia_g,gaia_bp,gaia_rp ^
  --contamination-model-mode top_hat ^
  --chunk-size 10000 ^
  --buffer-flush-interval 200 ^
  --use-dask ^
  --no-calculate-separations ^
  --run-build ^
  --run-query
```

Su macOS/Linux, usa backslash invece di `^` per continuare una riga:

```bash
photo-cat run \
  --config config.yaml \
  --input-catalog data/my_catalog.csv \
  --targets-input data/my_targets.csv \
  --out-dir output/my_run \
  --index-dir output/my_run \
  --ra-column ra \
  --dec-column dec \
  --mag-column phot_g_mean_mag \
  --field-of-view-arcsec 47 \
  --delta-mag 5
```

## Esempio di override colonne catalogo

Se il catalogo ha questi header:

```text
id,RAJ2000,DEJ2000,Gmag
```

esegui:

```bash
photo-cat run --config config.yaml ^
  --input-catalog data/catalog.csv ^
  --targets-input data/targets.csv ^
  --catalog-source-id-column id ^
  --ra-column RAJ2000 ^
  --dec-column DEJ2000 ^
  --mag-column Gmag
```

## Esempio solo query

Usalo quando l’indice esiste già e sono cambiati solo target o impostazioni di query:

```bash
photo-cat query --config config.yaml ^
  --index-dir output/my_run ^
  --targets-input data/new_targets.csv ^
  --target-source-id-column source_id ^
  --field-of-view-arcsec 60 ^
  --delta-mag 4
```

## Target manuali senza CSV target

Usa `--no-targets-input` con `--targets`:

```bash
photo-cat query --config config.yaml ^
  --index-dir output/my_run ^
  --no-targets-input ^
  --targets 1001,1002,1003 ^
  --field-of-view-arcsec 47 ^
  --delta-mag 5
```

Per ID target che contengono spazi, racchiudi l’argomento tra virgolette:

```bash
photo-cat query --config config.yaml --no-targets-input --targets "HD 216608A,HD 216608B"
```

## Esempio solo build

Usalo quando cambiano catalogo o raggio di build:

```bash
photo-cat build-index --config config.yaml ^
  --input-catalog data/catalog.csv ^
  --out-dir output/index_120arcsec ^
  --catalog-source-id-column source_id ^
  --ra-column ra ^
  --dec-column dec ^
  --mag-column phot_g_mean_mag ^
  --max-radius-arcsec 120 ^
  --chunk-size 50000 ^
  --use-dask
```

## Saltare build o query nella pipeline completa

Esegui solo la query tramite il comando pipeline:

```bash
photo-cat run --config config.yaml --no-run-build --run-query
```

Esegui solo la build tramite il comando pipeline:

```bash
photo-cat run --config config.yaml --run-build --no-run-query
```

## Sintassi degli override booleani

Le opzioni booleane supportano forma positiva e negativa:

```bash
--use-dask
--no-use-dask
--calculate-separations
--no-calculate-separations
--run-build
--no-run-build
--run-query
--no-run-query
--replace-running-pipeline
--no-replace-running-pipeline
```

## Riferimento completo degli override

| Valore YAML | Override CLI |
|---|---|
| `build_neighbors_index.io.input_catalog` | `--input-catalog PATH` |
| `build_neighbors_index.io.out_dir` | `--out-dir PATH` |
| `build_neighbors_index.io.usecolumns` | `--usecolumns source_id,ra,dec,mag` |
| `build_neighbors_index.io.columns.source_id` | `--catalog-source-id-column NAME` |
| `build_neighbors_index.io.columns.ra` | `--ra-column NAME` |
| `build_neighbors_index.io.columns.dec` | `--dec-column NAME` |
| `build_neighbors_index.io.columns.phot_g_mean_mag` | `--mag-column NAME` |
| `build_neighbors_index.settings.use_dask` | `--use-dask` / `--no-use-dask` |
| `build_neighbors_index.settings.calculate_separations` | `--calculate-separations` / `--no-calculate-separations` |
| `build_neighbors_index.settings.max_radius_arcsec` | `--max-radius-arcsec VALUE` |
| `build_neighbors_index.settings.chunk_size` | `--chunk-size VALUE` |
| `build_neighbors_index.settings.buffer_flush_interval` | `--buffer-flush-interval VALUE` |
| `query_contamination_from_index.io.INDEX_DIR` | `--index-dir PATH` |
| `query_contamination_from_index.io.TARGETS_INPUT` | `--targets-input PATH` o `--no-targets-input` |
| `query_contamination_from_index.io.targets` | `--targets ID1,ID2,ID3` |
| `query_contamination_from_index.io.target_source_id_column` | `--target-source-id-column NAME` |
| `query_contamination_from_index.settings.field_of_view_arcsec` | `--field-of-view-arcsec VALUE` |
| `query_contamination_from_index.settings.field_of_view_arcsec` | `--aperture-radius-arcsec VALUE` (alias più chiaro) |
| `query_contamination_from_index.settings.influence_radius_arcsec` | `--influence-radius-arcsec VALUE` |
| `query_contamination_from_index.settings.bandpass_transform_file` | `--bandpass-transform-file PATH` |
| `query_contamination_from_index.settings.delta_mag` | `--delta-mag VALUE` |
| `query_contamination_from_index.settings.include_missing_targets` | `--include-missing-targets` / `--no-include-missing-targets` |
| `execution.run_build` | `--run-build` / `--no-run-build` |
| `execution.run_query` | `--run-query` / `--no-run-query` |
| `execution.replace_running_pipeline` | `--replace-running-pipeline` / `--no-replace-running-pipeline` |
