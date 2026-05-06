# PHOTO-CAT - Photometric Contamination Analyzer Tool

PHOTO-CAT è uno strumento Python per la valutazione della contaminazione fotometrica in cataloghi astronomici. Il software costruisce un indice dei vicini a partire da un catalogo fotometrico e interroga le possibili sorgenti contaminanti intorno a un insieme selezionato di target.

Il progetto è pensato per analisi fotometriche locali, riproducibili e a livello di catalogo, con un'interfaccia grafica di configurazione, setup automatico del virtual environment e launcher specifici per Windows, macOS e Linux.

## Funzionalità

- Costruzione di un indice dei vicini da un catalogo fotometrico.
- Interrogazione della contaminazione intorno a sorgenti target.
- Configurazione delle run tramite interfaccia grafica.
- Supporto sia per un CSV di target sia per una lista manuale di source ID.
- Validazione dei file di input, dei nomi colonna, delle cartelle di output e dei percorsi dell'indice prima dell'esecuzione.
- Creazione e gestione automatica di un virtual environment Python locale.
- Rilevamento dello spostamento della cartella del progetto e ricostruzione automatica del virtual environment quando necessario.
- Messaggi di errore leggibili per i problemi di configurazione più comuni lato utente.

## Requisiti

PHOTO-CAT richiede:

- Python 3.10 o successivo
- Accesso a Internet durante la prima installazione delle dipendenze
- Un catalogo fotometrico in formato CSV

Il launcher crea una cartella `.venv` locale e installa lì tutte le dipendenze Python richieste. Il virtual environment è locale alla cartella del progetto e non è pensato per essere spostato tra percorsi diversi.

## Installazione e avvio

Scaricare lo ZIP dell'ultima release, estrarlo, quindi avviare il launcher relativo al proprio sistema operativo.

```text
Windows       START_WINDOWS.bat
macOS/Linux   sh START_UNIX.sh
```

Il launcher controlla l'installazione di Python, prepara il virtual environment locale, installa o verifica le dipendenze e apre il configuratore grafico.

Gli utenti standard non dovrebbero avere necessità di aprire le cartelle `src/` o `scripts/`.

## Dati in ingresso

PHOTO-CAT utilizza file CSV come input.

Lo schema predefinito del catalogo segue nomi colonna comuni in stile Gaia:

```text
source_id
ra
dec
phot_g_mean_mag
```

La colonna identificativa predefinita per i target è:

```text
source_id
```

I nomi delle colonne sono case-sensitive e devono corrispondere esattamente all'header del CSV. Se i file di input usano nomi differenti, possono essere modificati tramite il configuratore grafico.

## Configurazione

Il file principale di configurazione è:

```text
config.yaml
```

Il metodo raccomandato per modificarlo è l'interfaccia grafica.

Quando viene selezionato un catalogo CSV, PHOTO-CAT inizializza automaticamente i percorsi collegati:

```text
Targets CSV
Output/index folder
Query index folder
```

Questi valori restano modificabili prima dell'esecuzione.

È anche possibile utilizzare una lista manuale di valori `source_id` invece di un CSV di target.

## Output

PHOTO-CAT scrive l'indice dei vicini generato e i risultati della query nella cartella di output configurata.

La fase di query produce un file JSON contenente, per ogni target processato, le metriche di contaminazione e l'elenco delle sorgenti vicine che soddisfano i criteri impostati.

## Struttura del progetto

```text
START_WINDOWS.bat      Launcher Windows
START_UNIX.sh          Launcher macOS/Linux
START_HERE.txt         Note minime di avvio
config.yaml            Configurazione runtime
requirements.txt       Dipendenze Python
data/                  Piccoli file di riferimento
src/                   Codice sorgente
scripts/               Script di supporto ai launcher e alle piattaforme
docs/                  Documentazione aggiuntiva
```

## Note sulle piattaforme

### Windows

`START_WINDOWS.bat` prova a rilevare automaticamente Python. Se Python non è presente, il launcher tenta l'installazione prima tramite `winget`, poi tramite l'installer ufficiale di Python.

Se l'installazione automatica fallisce, installare manualmente Python 3.10 o successivo e abilitare:

```text
Add python.exe to PATH
```

Poi eseguire nuovamente `START_WINDOWS.bat`.

### macOS e Linux

Usare il launcher Unix condiviso:

```bash
sh START_UNIX.sh
```

Su macOS, i file di comando scaricati possono essere bloccati da Gatekeeper. Eseguire il launcher Unix tramite Terminale evita questo problema.

Su Linux, il launcher tenta di usare il package manager rilevato quando possibile, ma alcune distribuzioni possono comunque richiedere l'installazione manuale di Python, `pip`, `venv` e Tkinter.

## Gestione degli errori

PHOTO-CAT valida i problemi di configurazione più comuni prima e durante l'esecuzione, inclusi:

- file di input mancanti;
- colonne CSV mancanti o non corrispondenti;
- mismatch nei nomi colonna case-sensitive;
- cartelle di output non valide;
- cartelle dell'indice query incomplete;
- campi di coordinate o magnitudine non numerici;
- cartelle del progetto spostate con virtual environment non più valido.

Quando la cartella del progetto viene spostata dopo la creazione del virtual environment, PHOTO-CAT rileva la `.venv` non più valida, la rimuove e la ricrea nel nuovo percorso. File utente come `config.yaml`, `data/` e le cartelle di output non vengono eliminati.

## Documentazione

La documentazione aggiuntiva è disponibile in:

```text
docs/
```

Le note di release e pubblicazione sono disponibili in:

```text
docs/PUBLISHING.md
```

## Come citare

Includere la seguente citazione e il seguente acknowledgement in qualsiasi materiale pubblicato che faccia uso di PHOTO-CAT.

### Citazione

```text
<paper reference>
```

### Acknowledgement

```text
This research made use of Photo-cat, a Python package for photometric contamination analysis (<paper reference>), developed with the support of Blue Skies Space Ltd. (www.bssl.space).
```

Sostituire `<paper reference>` con il riferimento bibliografico definitivo quando disponibile.

## Licenza

Non è stata ancora specificata una licenza. Aggiungere un file `LICENSE` prima di distribuire PHOTO-CAT pubblicamente se si vogliono definire i termini di riuso, modifica o redistribuzione.
