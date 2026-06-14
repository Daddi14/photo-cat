# Uso da riga di comando

PHOTO-CAT può essere eseguito da riga di comando con un file YAML di configurazione e override diretti opzionali.

La GUI resta il punto di ingresso consigliato per l’uso desktop normale. La CLI è pensata per esecuzioni da script, sistemi remoti, cluster, pipeline riproducibili e workflow batch.

## Comandi base

```bash
photo-cat --help
photo-cat configure
photo-cat run --config config.yaml
photo-cat build-index --config config.yaml
photo-cat query --config config.yaml
photo-cat doctor
```

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

## Gestione dei percorsi

I percorsi passati tramite override CLI sono risolti rispetto alla cartella da cui viene eseguito il comando.

Esempio:

```bash
photo-cat run --config configs/run.yaml --input-catalog data/catalog.csv
```

`data/catalog.csv` viene risolto a partire dalla cartella corrente del terminale.

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
  --max-radius-arcsec 120 ^
  --field-of-view-arcsec 47 ^
  --delta-mag 5 ^
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
| `build_neighbors_index.io.KDTREE_FILENAME` | `--kdtree-filename NAME` |
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
| `query_contamination_from_index.settings.delta_mag` | `--delta-mag VALUE` |
| `execution.run_build` | `--run-build` / `--no-run-build` |
| `execution.run_query` | `--run-query` / `--no-run-query` |
| `execution.replace_running_pipeline` | `--replace-running-pipeline` / `--no-replace-running-pipeline` |
