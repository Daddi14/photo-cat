<div align="center">

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/photo-cat-logo-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="assets/photo-cat-logo-light.png">
    <img src="assets/photo-cat-logo-colored.png" alt="Logo PHOTO-CAT" width="200">
  </picture>
</p>

[English](README.md) · [Italiano](README_IT.md)

**Photometric Contamination Analyzer Tool**

PHOTO-CAT crea un indice dei vicini a partire da un catalogo astronomico e valuta il rischio di contaminazione da sorgenti vicine per target fotometrici selezionati.

[Download e utilizzo](docs/Download-and-usage_IT.md) · [Riprodurre i risultati del paper](docs/REPRODUCE_PAPER_RESULT_IT.md) · [Riga di comando](docs/Command-line_IT.md) · [Dati di input](docs/Input-data_IT.md) · [Risoluzione problemi](docs/Troubleshooting_IT.md)

![Python](https://img.shields.io/badge/python-3.10--3.13-blue)
![Piattaforme](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Runtime](https://img.shields.io/badge/runtime-project--local-green)
![Interfaccia](https://img.shields.io/badge/interface-GUI%20%2B%20CLI-informational)

</div>

---

## Panoramica

PHOTO-CAT è uno strumento Python locale per la valutazione del rischio di contaminazione fotometrica a livello di catalogo e per lo screening dei target.

Può creare un indice dei vicini da un catalogo di sorgenti, interrogare target selezionati e scrivere un riepilogo JSON con metriche di contaminazione catalogo/apertura e sorgenti vicine che rispettano i limiti configurati di campo di vista e magnitudine.

Il modello attuale di PHOTO-CAT 2.0.0 ha un ambito volutamente definito: usa magnitudini di catalogo, un'apertura circolare e una PSF gaussiana circolare 2D opzionale, il cui flusso decade con la distanza angolare dal centro dell'apertura. Un raggio di influenza ricavato dalla larghezza della PSF può includere il leakage pesato di sorgenti vicine fuori dall'apertura. Un profilo calibrato opzionale con polinomio di colore può stimare una banda di missione con validità e provenienza. Non esegue convoluzione con PSF asimmetriche o variabili, modellazione dei pixel, luce diffusa o integrazione spettrale completa sulla banda. Considera l'output come metrica di screening/rischio salvo che input di missione calibrati supportino i modelli selezionati.

PHOTO-CAT è pensato per un utilizzo locale e riproducibile. Include launcher semplici, una finestra grafica di configurazione, setup automatico delle dipendenze, gestione del runtime locale al progetto, manifest versionati dell'indice e metadata sidecar delle query con versione del pacchetto, impostazioni, manifest dell'indice e ambito del modello.

> **Migrazione alla versione 2:** gli indici creati da PHOTO-CAT 1.x devono essere ricostruiti. La versione 2 usa un formato versionato e non eseguibile e rifiuta intenzionalmente i precedenti file pickle/object-array.

## Download e primo avvio

1. Scarica l’archivio dell’ultima release.
2. Estrai l’archivio.
3. Avvia il programma per il tuo sistema operativo:
   - Windows: doppio clic su `START_WINDOWS.bat`
   - macOS/Linux: apri il Terminale nella cartella ed esegui `sh START_UNIX.sh`
4. Seleziona il CSV del catalogo nella configurazione grafica.
5. Controlla i nomi delle colonne rilevati.
6. Clicca `Salva e avvia la pipeline`.

Vedi [Download e utilizzo](docs/Download-and-usage_IT.md) per una guida più completa.

## Funzioni

- Crea un indice dei vicini da un catalogo fotometrico.
- Esegue screening dei target rispetto a sorgenti di catalogo vicine che possono contaminare un'apertura circolare.
- Riporta sia il flusso dei contaminanti selezionati sia il flusso di tutti i vicini dentro il raggio.
- Confronta opzionalmente metriche di flusso a livello di catalogo tra bande di magnitudine salvate.
- Applica una trasformazione empirica di colore con provenienza verso una banda di missione.
- Usa un modello di screening della contaminazione top-hat o con PSF gaussiana circolare 2D.
- Riassume i JSON dei risultati in statistiche text, JSON o CSV.
- Genera plot SVG senza dipendenze aggiuntive e report HTML/Markdown.
- Genera distribuzioni dei conteggi e delle separazioni pronte per la
  pubblicazione, insieme a una mappa colourblind-safe con marker ridondanti.
- Esporta tabelle di risultati target in CSV o Parquet per notebook e strumenti esterni.
- Cattura provenance JSON del catalogo con checksum, conteggi righe, statistiche colonne e checksum ADQL opzionale.
- Genera pacchetti riproducibili per articolo/revisione con riassunti, plot, report e checksum.
- Unisce cataloghi supplementari di stelle brillanti prima della creazione dell'indice.
- Ordina i target in decisioni esplicite accept/review/reject per lo screening.
- Valida la contaminazione prevista rispetto a tabelle di missione/riferimento fornite dall'utente.
- Esegue benchmark riproducibili con tempi e allocazioni Python di picco.
- Converte i benchmark in tabelle Markdown o CSV pronte per l'articolo.
- Configura le esecuzioni tramite interfaccia grafica.
- Passa tra inglese e italiano per GUI, guida dei comandi, messaggi della console, avvisi ed errori previsti.
- Consulta tooltip introduttivi su ogni impostazione, valore, sezione e azione della GUI, con spiegazioni pratiche dei termini astronomici.
- Mantiene in inglese le etichette scientifiche dei grafici con entrambe le lingue dell'interfaccia, per produrre figure coerenti e pronte per la pubblicazione.
- Esegui lo stesso workflow da una CLI per automazione e sistemi remoti, con override diretti per ogni valore di configurazione.
- Usa un CSV di target oppure una lista manuale di source ID.
- Valida file di input, nomi delle colonne, cartelle di output e percorsi dell’indice.
- Mantiene le dipendenze isolate nella cartella `.venv` del progetto.
- Usa un runtime locale al progetto quando non è disponibile un Python adatto.
- Rileva ambienti virtuali obsoleti o spostati e li ricrea in modo sicuro.
- Produce output console leggibile e messaggi d’errore pensati per l’utente.

## File

Questa distribuzione include i principali file e cartelle seguenti:

- `README.md`, la documentazione principale in inglese.
- `README_IT.md`, la documentazione principale in italiano.
- `START_WINDOWS.bat`, il launcher principale per Windows.
- `START_UNIX.sh`, il launcher principale per macOS/Linux.
- `config.yaml`, il file di configurazione gestito dalla GUI.
- `data/`, CSV di esempio per test rapidi.
- `docs/`, documentazione utente e manutentore.
- `tests/`, test automatici per caricamento configurazione e pipeline di esempio.
- `.github/workflows/`, workflow di integrazione continua e pubblicazione del pacchetto.
- `scripts/`, helper dei launcher per piattaforma.
- `src/`, codice sorgente Python di PHOTO-CAT.
- `LICENSE`, testo completo della licenza GPL-3.0.
- `REUSE.toml`, metadata SPDX/REUSE per licenza e copyright.
- `CITATION.cff`, metadata di citazione leggibile da GitHub.
- `CODE_OF_CONDUCT.md`, `CONTRIBUTING.md` e `SECURITY.md`, file comunitari e manutentivi del repository.

Cartelle generate a runtime come `.venv/`, `.runtime/`, log e file di output sono locali e non vanno committate.

## Dati di input

PHOTO-CAT richiede file CSV in input.

Le colonne predefinite del catalogo seguono nomi comuni in stile Gaia:

- `source_id`
- `ra`
- `dec`
- `phot_g_mean_mag`

I nomi delle colonne sono case-sensitive e devono corrispondere esattamente all’header del CSV. Se i tuoi file usano nomi diversi, cambiali nella configurazione grafica prima di avviare la pipeline.

Vedi [Dati di input](docs/Input-data_IT.md) per i dettagli.

## Output

PHOTO-CAT scrive i file di indice generati e i risultati delle query nella cartella di output configurata.

La fase di query produce un file JSON con una voce per ogni target processato. Ogni voce include i dati del target, le metriche di contaminazione catalogo/apertura e l’elenco delle sorgenti vicine qualificate. Un metadata sidecar viene scritto anche in `output/metadata/` per supportare la riproducibilità.

I risultati possono essere post-processati con:

```bash
photo-cat summarize output/index/results/result.json
photo-cat export output/index/results/result.json --format csv --output output/result.csv
photo-cat plot output/index/results/result.json --kind contaminant-counts
photo-cat publication-plots output/index/results/result.json --aperture-arcsec 47 --output-dir output/publication_plots
photo-cat provenance data/catalog.csv --adql-file examples/reproducibility/gaia_dr3_g17_selection.adql --output output/catalog_provenance.json
photo-cat report output/index/results/result.json --format html
photo-cat benchmark --config config.yaml --output output/benchmark.json
photo-cat benchmark-table output/benchmark.json --output output/benchmark_table.md
photo-cat reproduce --result-json output/index/results/result.json --output-dir output/reproduction
photo-cat merge-bright-stars data/gaia.csv data/bright.csv --output data/merged_catalog.csv
photo-cat screen output/index/results/result.json --output output/screening.csv
photo-cat validate-results output/index/results/result.json data/reference.csv --output output/validation.json
```

Vedi [Pipeline e output](docs/Pipeline-and-output_IT.md) per i dettagli.

## Runtime e gestione Python

PHOTO-CAT usa Python localmente ed evita di modificare l’installazione Python di sistema dell’utente.

I launcher usano un Python esistente solo quando è supportato e supera i controlli richiesti. Le versioni supportate sono Python 3.10 fino a 3.13.

Se non è disponibile un Python adatto, PHOTO-CAT usa un runtime privato sotto `.runtime/` e installa il pacchetto e le dipendenze solo dentro `.venv/`.

PHOTO-CAT non modifica `PATH` in modo permanente, non aggiorna Python dell’utente, non disinstalla Python dell’utente e non installa pacchetti nel Python di sistema.

Vedi [Runtime e Python](docs/Runtime-and-Python_IT.md) per i dettagli.

## Uso da riga di comando

Dopo l’installazione del pacchetto, la CLI unificata è disponibile come `photo-cat`.

Comandi comuni:

```bash
photo-cat configure
photo-cat run --config config.yaml
photo-cat run --config config.yaml --input-catalog data/catalog.csv --ra-column RAJ2000 --dec-column DEJ2000 --mag-column Gmag --field-of-view-arcsec 60 --delta-mag 4
photo-cat build-index --config config.yaml --input-catalog data/catalog.csv --out-dir output/index
photo-cat query --config config.yaml --index-dir output/index --targets-input data/targets.csv --field-of-view-arcsec 47 --delta-mag 5
photo-cat query --config config.yaml --aperture-radius-arcsec 47 --contamination-model-mode gaussian_psf --gaussian-fwhm-arcsec 20 --influence-sigma 3
photo-cat doctor
```

I launcher nella root restano il punto di ingresso consigliato per gli utenti locali non tecnici. La CLI è pensata per automazione, macchine remote e workflow riproducibili. Supporta override diretti di runtime per ogni valore di `config.yaml`; vedi [Uso da riga di comando](docs/Command-line_IT.md). Il comando doctor supporta sia controlli di pacchetto sia controlli della cartella progetto. Usa `photo-cat doctor --format json` per diagnostica leggibile da macchina nell’automazione.

## Documentazione

Documentazione utente:

- [Download e utilizzo](docs/Download-and-usage_IT.md)
- [Dati di input](docs/Input-data_IT.md)
- [Configurazione](docs/Configuration_IT.md)
- [Pipeline e output](docs/Pipeline-and-output_IT.md)
- [Runtime e Python](docs/Runtime-and-Python_IT.md)
- [Risoluzione problemi](docs/Troubleshooting_IT.md)

Documentazione manutentori:

- [Pubblicazione PHOTO-CAT](docs/PUBLISHING_IT.md)
- [Architettura e confini dei test](docs/Architecture_IT.md)
- [Contratti pubblici](docs/Public-Contracts_IT.md)
- [Workflow di sviluppo](docs/Development_IT.md)
- [Contribuire](CONTRIBUTING.md)

## Risoluzione problemi

Per problemi comuni di avvio, dipendenze, Tkinter, CSV e ambienti virtuali, vedi [Risoluzione problemi](docs/Troubleshooting_IT.md).

## Riprodurre i risultati del paper

PHOTO-CAT include una procedura per principianti che ricrea i prodotti coordinati del paper a partire dai dati Gaia DR3:

1. scarica il catalogo Gaia G=17 usato per cercare i contaminanti vicini;
2. scarica un campione target Gaia G=12 separato;
3. configura ed esegui la pipeline di costruzione/query;
4. genera distribuzione dei contaminanti, separazioni e mappa celeste tramite **Grafici da pubblicazione**;
5. conserva query, configurazione, metadata, manifest e checksum necessari alla riproducibilità.

Segui la guida completa passo per passo: **[Riprodurre i risultati del paper](docs/REPRODUCE_PAPER_RESULT_IT.md)**.

## Citazione

Includi la seguente citazione e il seguente ringraziamento in qualunque pubblicazione che utilizzi PHOTO-CAT.

Citazione:

`<publication reference>`

Ringraziamento:

`This research made use of PHOTO-CAT, a Python package for catalogue-level photometric contamination risk assessment and target screening (<publication reference>), developed with the support of Blue Skies Space Ltd. (www.bssl.space).`

Sostituisci `<publication reference>` con il riferimento finale della pubblicazione quando disponibile.

## Ringraziamenti

Gli autori ringraziano:

- E. Drago per i contributi fondamentali all'implementazione del software, al processo di testing e al perfezionamento tecnico di PHOTO-CAT.

- J. Burgio per la progettazione e la creazione del logo e dell'identità visiva di PHOTO-CAT.

## Licenza

PHOTO-CAT è distribuito solo con licenza GNU General Public License v3.0. Vedi [`LICENSE`](LICENSE) per il testo completo della licenza.
