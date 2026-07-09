# Dati di input

PHOTO-CAT lavora con file CSV in input.

## Catalogo CSV

Il CSV catalogo è la tabella sorgente principale usata per creare l’indice dei vicini.

Le colonne attese di default sono:

- `source_id`
- `ra`
- `dec`
- `phot_g_mean_mag`

I valori `source_id` devono essere univoci anche dopo la normalizzazione numerica
(`1` e `001` sono ambigui). `ra` deve essere finito e compreso in `[0, 360)`,
`dec` in `[-90, 90]` e `phot_g_mean_mag` deve essere finito.

## CSV target

Il CSV target identifica le sorgenti da interrogare usando l’indice dei vicini creato.

La colonna identificatore target predefinita è:

- `source_id`

I valori target devono corrispondere agli ID del catalogo.

## Target manuali

PHOTO-CAT può anche usare una lista manuale di source ID target invece di un CSV target.

È utile per controlli rapidi o piccole liste di target.

## Nomi colonne

I nomi delle colonne sono case-sensitive. Devono corrispondere esattamente all’header del CSV.

Se il tuo catalogo usa nomi diversi, configurali nella configurazione grafica prima di eseguire la pipeline.

## File di esempio

La cartella `data/` include piccoli file di esempio:

- `example_catalog.csv`
- `example_targets.csv`

Servono solo a testare il workflow. Sostituiscili con cataloghi e target reali per l’analisi.

## Selezioni di catalogo riproducibili

PHOTO-CAT registra il digest SHA-256 del CSV catalogo nel manifest dell'indice
versione 2, ma non può dedurre come quel CSV sia stato prodotto. Per analisi
pubblicabili o verificabili, conserva la provenienza del catalogo accanto alla
run:

- release e servizio di catalogo esatti, per esempio una tabella Gaia DR/EDR;
- query esatta, tagli di qualità, limiti di magnitudine, regione di cielo e
  limiti di righe;
- eventuali input di cross-match, per esempio selezioni dal Bright Star Catalog;
- nome del CSV esportato e checksum;
- `config.yaml` o comando CLI usato per build e query.

Usa `photo-cat --version`, `photo-cat build-index ...` e `photo-cat query ...`
in script o notebook in modo che la sequenza di comandi sia rieseguibile. I
metadata sidecar in `INDEX_DIR/output/metadata/` registrano versione di PHOTO-CAT,
impostazioni della query, manifest dell'indice e ambito del modello per ogni
file risultato.

Vedi `docs/gaia_selection_example.txt` per un template testuale da compilare con
le selezioni Gaia/Bright Star Catalog esatte usate da un articolo. La cartella
`examples/paper/` contiene anche template ADQL/config e un piccolo script per
rigenerare riassunti, plot SVG e report da un JSON di risultati query.
