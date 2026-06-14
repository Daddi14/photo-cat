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

PHOTO-CAT crea un indice dei vicini a partire da un catalogo astronomico e interroga le sorgenti vicine che possono contaminare target fotometrici selezionati.

[Download e utilizzo](docs/Download-and-usage_IT.md) · [Riga di comando](docs/Command-line_IT.md) · [Dati di input](docs/Input-data_IT.md) · [Risoluzione problemi](docs/Troubleshooting_IT.md)

![Python](https://img.shields.io/badge/python-3.10--3.13-blue)
![Piattaforme](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Runtime](https://img.shields.io/badge/runtime-project--local-green)
![Interfaccia](https://img.shields.io/badge/interface-GUI%20%2B%20CLI-informational)

</div>

---

## Panoramica

PHOTO-CAT è uno strumento Python locale per l’analisi della contaminazione fotometrica a livello di catalogo.

Può creare un indice dei vicini da un catalogo di sorgenti, interrogare target selezionati e scrivere un riepilogo JSON con metriche di contaminazione e sorgenti vicine che rispettano i limiti configurati di campo di vista e magnitudine.

PHOTO-CAT è pensato per un utilizzo locale e riproducibile. Include launcher semplici, una finestra grafica di configurazione, setup automatico delle dipendenze e gestione del runtime locale al progetto, così le installazioni Python dell’utente o del sistema non vengono modificate.

## Download e primo avvio

1. Scarica l’archivio dell’ultima release.
2. Estrai l’archivio.
3. Avvia il programma per il tuo sistema operativo:
   - Windows: doppio clic su `START_WINDOWS.bat`
   - macOS/Linux: apri il Terminale nella cartella ed esegui `sh START_UNIX.sh`
4. Seleziona il CSV del catalogo nella configurazione grafica.
5. Controlla i nomi delle colonne rilevati.
6. Clicca `Save + run`.

Vedi [Download e utilizzo](docs/Download-and-usage_IT.md) per una guida più completa.

## Funzioni

- Crea un indice dei vicini da un catalogo fotometrico.
- Interroga sorgenti potenzialmente contaminanti attorno ai target selezionati.
- Configura le esecuzioni tramite interfaccia grafica.
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

La fase di query produce un file JSON con una voce per ogni target processato. Ogni voce include i dati del target, le metriche di contaminazione e l’elenco delle sorgenti vicine qualificate.

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
photo-cat doctor
```

I launcher nella root restano il punto di ingresso consigliato per gli utenti locali non tecnici. La CLI è pensata per automazione, macchine remote e workflow riproducibili. Supporta override diretti di runtime per ogni valore di `config.yaml`; vedi [Uso da riga di comando](docs/Command-line_IT.md). Il comando doctor supporta sia controlli di pacchetto sia controlli della cartella progetto.

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

## Risoluzione problemi

Per problemi comuni di avvio, dipendenze, Tkinter, CSV e ambienti virtuali, vedi [Risoluzione problemi](docs/Troubleshooting_IT.md).

## Citazione

Includi la seguente citazione e il seguente ringraziamento in qualunque pubblicazione che utilizzi PHOTO-CAT.

Citazione:

`<paper reference>`

Ringraziamento:

`This research made use of PHOTO-CAT, a Python package for photometric contamination analysis (<paper reference>), developed with the support of Blue Skies Space Ltd. (www.bssl.space).`

Sostituisci `<paper reference>` con il riferimento finale dell’articolo quando disponibile.

## Ringraziamenti

Gli autori ringraziano:

- E. Drago per i contributi fondamentali all'implementazione del software, al processo di testing e al perfezionamento tecnico di PHOTO-CAT.

- J. Burgio per la progettazione e la creazione del logo e dell'identità visiva di PHOTO-CAT.

## Licenza

PHOTO-CAT è distribuito solo con licenza GNU General Public License v3.0. Vedi [`LICENSE`](LICENSE) per il testo completo della licenza.
