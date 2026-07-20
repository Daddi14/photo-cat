# Eseguibile Windows di PHOTO-CAT (spike PyInstaller)

Questa cartella impacchetta PHOTO-CAT in un eseguibile Windows autonomo, così gli
utenti possono usarlo senza installare Python. È uno **spike validato**: la build
funziona già oggi dall'inizio alla fine, con alcune decisioni di produzione
elencate più sotto.

## Build

```bat
packaging\build_windows.bat
```

Questo installa PyInstaller nell'ambiente virtuale locale `.venv` ed esegue
`packaging\photo-cat.spec`. Il risultato è una distribuzione a cartella singola:

```
dist\photo-cat\photo-cat.exe
```

`photo-cat.exe` è la stessa CLI del comando `photo-cat` installato, quindi:

- `photo-cat.exe --version`, `photo-cat.exe doctor`, `photo-cat.exe summarize ...`
  e ogni altro sottocomando funzionano direttamente.
- `photo-cat.exe configure` apre il configuratore grafico.

## Cosa è stato verificato

Compilato con PyInstaller 6.21 su Windows 10, Python 3.13:

- **Compila senza errori** in un pacchetto a cartella singola di **~277 MB**.
- `photo-cat.exe doctor` riporta **tutti i controlli superati** -- tkinter, NumPy,
  pandas, SciPy, tqdm, PyYAML, **PyArrow** e **Dask** sono tutti inclusi e
  importabili.
- I comandi CLI vengono eseguiti, incluso il backend matplotlib
  (`photo-cat.exe plot <result>.json --backend matplotlib`).
- La **GUI si avvia** dall'eseguibile e mostra il logo (gli asset sono inclusi e
  letti dalla directory di estrazione di PyInstaller).
- La GUI è **consapevole del freeze** (`sys.frozen`): invoca i comandi degli
  strumenti e della pipeline tramite l'eseguibile stesso
  (`photo-cat.exe <sottocomando>`) invece di `python -m photo_cat.cli`, e
  legge/scrive `config.yaml` e gli output accanto all'eseguibile.

## Come è organizzato

- `entry_photo_cat.py` -- punto di ingresso del freeze; delega a
  `photo_cat.cli.main`.
- `photo-cat.spec` -- include i metadati dell'app (supporto a
  `importlib.metadata`), raccoglie completamente `dask` e `pyarrow`
  (matplotlib/scipy/numpy/pandas usano gli hook integrati di PyInstaller) e
  include gli asset del logo.
- `src/photo_cat/configure_gui.py` -- quando è in freeze, risolve gli asset da
  `sys._MEIPASS`, ancora `config.yaml` e gli output accanto all'eseguibile e
  costruisce le invocazioni dei sottocomandi verso l'eseguibile stesso.

## Decisioni di produzione (non fatte in questo spike)

- **Impacchettamento di config e dati.** Un'app in freeze ancora `config.yaml` e
  le cartelle di output accanto all'eseguibile. Distribuire un `config.yaml`
  predefinito (e, facoltativamente, i dati di esempio) insieme all'eseguibile,
  oppure aggiungere un passaggio di configurazione al primo avvio. La build
  **non** include intenzionalmente `data/` né un `config.yaml` predefinito.
- **Finestra della console.** Lo spec usa `console=True` affinché l'output della
  CLI sia visibile; di conseguenza la GUI si apre con una finestra di console.
  Per una GUI puramente a doppio clic, distribuire un secondo eseguibile in
  modalità finestra (`console=False`) o un piccolo launcher.
- **Dimensione / distribuzione.** La cartella singola (~277 MB) è la forma
  consigliata e affidabile; comprimerla in zip per la distribuzione. `--onefile`
  produce un singolo eseguibile ma con avvio più lento (si estrae a ogni
  esecuzione) e maggiori attriti con gli antivirus.
- **Firma del codice.** Gli eseguibili PyInstaller non firmati possono attivare
  SmartScreen e le euristiche degli antivirus. Firmare l'eseguibile per la
  distribuzione pubblica.
- **Artefatto in CI.** Compilare l'eseguibile su un runner Windows e caricarlo
  come artefatto di release è un naturale passo successivo; qui non è
  intenzionalmente integrato nella CI perché la build è pesante e lenta.
- **Pipeline end-to-end dalla GUI in freeze.** L'auto-invocazione
  `photo-cat.exe run` è predisposta, ma un'esecuzione completa build+query dalla
  GUI in freeze andrebbe validata con un dataset reale e un `config.yaml`
  adiacente prima del rilascio.

## Raccomandazione

Una build Windows a cartella singola è **fattibile e a basso rischio**. Il lavoro
rimanente riguarda le politiche di impacchettamento (disposizione di config e
dati, GUI in modalità finestra facoltativa, firma del codice), non incognite
tecniche.
