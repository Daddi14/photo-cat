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

Una build completata scrive i file dell'indice dei vicini documentati nella directory di output configurata. La modalità query dipende da questo layout, quindi le modifiche richiedono un piano di migrazione, compatibilità o una rottura documentata di major version.

## Risultati della query

La fase query scrive file JSON in `INDEX_DIR/output`.

Ogni risultato per target preserva i campi documentati per:

- ID della sorgente target;
- coordinate e magnitudine del target quando disponibili;
- `flux_fraction_extra`;
- `num_contaminants`;
- record dei contaminanti con ID sorgente, coordinate, magnitudine e separazione.

I test di regressione devono proteggere i nomi dei campi, l'ordine dei risultati quando documentato e le convenzioni numeriche che influenzano l'interpretazione scientifica.

## Diagnostica e launcher

`photo-cat doctor` supporta sia la modalità pacchetto installato sia la modalità progetto sorgente. Il suo stato di successo/fallimento documentato e le diagnostiche pratiche sono comportamento visibile agli utenti.

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
