<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Contratti pubblici

Questo documento identifica il comportamento di PHOTO-CAT che i contributori devono preservare, salvo quando una release documenta esplicitamente una modifica di compatibilità intenzionale.

Non è una promessa di API per ogni funzione interna. Definisce i confini visibili agli utenti protetti dai test di regressione.

## Interfaccia a riga di comando

I seguenti comandi e alias sono pubblici:

```text
photo-cat configure
photo-cat gui
photo-cat run
photo-cat build-index
photo-cat query
photo-cat summarize
photo-cat summary
photo-cat export
photo-cat plot
photo-cat publication-plots
photo-cat report
photo-cat screen
photo-cat rank
photo-cat validate-results
photo-cat validate
photo-cat benchmark
photo-cat benchmark-table
photo-cat provenance
photo-cat doctor
photo-cat --version
```

Le opzioni documentate della riga di comando, inclusi gli override diretti di runtime, devono mantenere il loro significato. Sono consentite nuove opzioni quando non modificano silenziosamente il comportamento dei comandi esistenti.

Gli errori di input utente previsti devono restituire stato `1` e stampare un messaggio conciso `ERROR:` sullo standard error. I comandi completati correttamente restituiscono stato `0`.

## Configurazione

Le sezioni di primo livello in `config.yaml` sono pubbliche:

```text
build_neighbors_index
query_contamination_from_index
execution
```

Le chiavi documentate in queste sezioni, il comportamento dei percorsi relativi e le regole di validazione fanno parte del modello di configurazione supportato. È preferibile aggiungere impostazioni piuttosto che rinominare o reinterpretare silenziosamente quelle esistenti.

### Regole di risoluzione dei percorsi

- I percorsi relativi memorizzati in `config.yaml`, inclusi catalogo, target, output build e indice query, sono risolti rispetto alla directory che contiene quel file config.
- Un percorso CLI esplicito `--config` e gli override diretti dei percorsi CLI sono risolti rispetto alla directory di lavoro da cui viene invocato `photo-cat`.
- I file di risultato della query vengono creati solo sotto `INDEX_DIR/output`; un file che occupa quel percorso è un errore di validazione.
- La validazione della directory dell’indice avviene prima che l’esecuzione numerica della query apra array dell’indice o memory map.
- Leggere o validare una configurazione non deve creare directory di output, cambiare la directory di lavoro del chiamante o modificare in modo permanente `PHOTO_CAT_CONFIG`.
- Gli override CLI diretti vengono derivati solo per un comando e non riscrivono il file `config.yaml` sorgente.
- I processi figli della pipeline ricevono la config selezionata in modo esplicito; comandi ripetuti nello stesso processo non devono ereditare un override precedente.

## Output della build dell'indice

Una build completata scrive i file documentati dell'indice dei vicini nella directory di output configurata. Il formato versione 2 richiede un `index_manifest.json` completo e array NumPy sicuri senza oggetti. Gli indici versione 1 devono essere ricostruiti e non vengono mai deserializzati.

## Risultati della query

La fase query scrive file JSON in `INDEX_DIR/output`.

Ogni risultato per target preserva i campi documentati per:

- ID della sorgente target;
- coordinate e magnitudine del target quando disponibili;
- `flux_fraction_selected`;
- `flux_fraction_all_neighbors`;
- `flux_fraction_extra`;
- metriche pesate additive `flux_fraction_inside_aperture`,
  `flux_fraction_outside_aperture` e `flux_fraction_total_weighted`;
- `num_neighbors_in_radius`;
- conteggi dei vicini nel raggio di influenza e fuori dall'apertura;
- `num_contaminants_selected`;
- `num_contaminants`;
- record dei contaminanti con ID sorgente, coordinate, magnitudine e separazione;
- sorgenti selezionate fuori dall'apertura identificate separatamente quando è
  configurato un raggio di influenza;
- magnitudini additive per banda di target/contaminanti e dizionari di flusso
  nella banda trasformata quando è configurato un profilo empirico;
- campi di provenienza `bandpass_transform_status`,
  `bandpass_transform_profile` e `bandpass_transformed_band`;
- alias scalari `*_transformed` utilizzabili dagli strumenti di screening e
  validazione;
- righe target non risolte quando richieste esplicitamente, con `status` uguale
  a `missing_from_index` o `invalid_target_id`.

Ogni query scrive anche un metadata sidecar per la riproducibilità in
`INDEX_DIR/output/metadata/`, con schema versione `1`. Il sidecar include
versione di PHOTO-CAT, configurazione della query, numero di target processati,
manifest dell'indice, percorso del risultato e note esplicite sull'ambito del
modello. Il sidecar è additivo e non deve trasformare il JSON dei risultati da
lista di target a oggetto wrapper.

I test di regressione devono proteggere i nomi dei campi, l'ordine dei risultati quando documentato e le convenzioni numeriche che influenzano l'interpretazione scientifica.

## Prodotti derivati dai risultati

`photo-cat summarize` legge un JSON di risultati target e produce statistiche
aggregate text, JSON o CSV. `photo-cat export` scrive tabelle target piatte CSV
o Parquet. `photo-cat plot` legge un JSON di risultati target e scrive SVG per i
tipi documentati di default, con backend matplotlib per output raster e da pubblicazione.
`photo-cat report` scrive report HTML o Markdown da un JSON di risultati target.
`photo-cat benchmark` scrive un documento JSON con schema versione `1`, durate
delle fasi, codici di stato, metadata di piattaforma, versione PHOTO-CAT, picco
di allocazioni Python via `tracemalloc` e campioni RSS opzionali via psutil.
`photo-cat provenance` scrive un JSON versionato con checksum del catalogo,
dimensione/header, conteggi nulli, range numerici, conteggi source ID duplicati
e checksum opzionale del file ADQL/query.

`photo-cat screen` scrive ranking dei target con versione dello schema, soglie,
decisioni, punteggi e motivazioni esplicite. `photo-cat validate-results` scrive
statistiche di confronto con versione dello schema rispetto a un CSV di
riferimento fornito dall'utente e può esportare le righe abbinate con i residui.

`photo-cat publication-plots` accetta un JSON di query e la relativa apertura e
scrive distribuzioni dei conteggi, delle separazioni, densità normalizzate per
area e mappe del cielo con un manifest dotato di checksum. Le classi della mappa
sono codificate tramite colore, forma e dimensione dei marker.

## Diagnostica e launcher

`photo-cat doctor` supporta sia la modalità pacchetto installato sia la modalità progetto sorgente. Il suo stato di successo/fallimento documentato e le diagnostiche pratiche sono comportamento visibile agli utenti.

`photo-cat doctor --format json` è un contratto pubblico per l'automazione. Emette un unico documento JSON con schema versione `1`, le chiavi di primo livello stabili `schema_version`, `ok`, `checks` e `summary`, e stati dei controlli `pass`, `warn`, `fail` oppure `info`. Un errore diagnostico restituisce stato `1`; gli avvisi non modificano lo stato riuscito `0`.

I launcher Windows e Unix rimangono punti di ingresso supportati per l'uso locale non tecnico. Le modifiche interne non devono richiedere agli utenti di comprendere l'ambiente virtuale di sviluppo.

## Il codice interno può cambiare

Nomi di helper privati, organizzazione dei moduli, layout delle dataclass e dettagli di implementazione possono cambiare quando il comportamento pubblico viene preservato. I test unitari possono verificare questi helper, ma i test di regressione devono essere la principale protezione dei contratti indicati sopra.

## Modificare un contratto

Prima di modificare un contratto pubblico:

1. spiega l'impatto sulla compatibilità nella pull request;
2. aggiorna la documentazione inglese e italiana;
3. aggiorna o aggiungi test di regressione;
4. includi note di migrazione quando gli utenti potrebbero avere configurazione, indice o file di output esistenti;
5. scegli una versione coerente con l'impatto sulla compatibilità.
