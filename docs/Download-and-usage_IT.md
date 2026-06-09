# Download e utilizzo

## Scaricare e iniziare con PHOTO-CAT

PHOTO-CAT è pensato per essere usato da un archivio release estratto localmente.

## Avvio rapido

1. Scarica l’archivio dell’ultima release.
2. Estrai l’archivio in una cartella scrivibile.
3. Avvia PHOTO-CAT:
   - Windows: doppio clic su `START_WINDOWS.bat`
   - macOS/Linux: apri il Terminale nella cartella ed esegui `sh START_UNIX.sh`
4. Seleziona il catalogo CSV nella GUI.
5. Controlla che i nomi delle colonne corrispondano all’header del CSV.
6. Clicca `Save + run`.

## Primo avvio

Il primo avvio può richiedere alcuni minuti.

PHOTO-CAT prepara un ambiente locale del progetto, installa il pacchetto e le dipendenze in `.venv/`, e usa `.runtime/` solo se non trova un Python supportato.

## Windows

Su Windows, usa il launcher principale:

`START_WINDOWS.bat`

Il launcher apre la console di setup, prepara l’ambiente locale e avvia la configurazione grafica.

## macOS/Linux

Su macOS e Linux, apri il Terminale nella cartella del progetto ed esegui:

`sh START_UNIX.sh`

Il launcher usa Bash quando disponibile e prepara l’ambiente locale prima di aprire la GUI.

## Esecuzione della pipeline

Dalla GUI:

1. seleziona il catalogo CSV
2. controlla i nomi delle colonne
3. seleziona o conferma i target
4. controlla cartella di output e impostazioni
5. clicca `Save + run`

PHOTO-CAT avvia la pipeline in una finestra console separata quando possibile.

## Aggiornare PHOTO-CAT

Per aggiornare PHOTO-CAT, sostituisci i file del progetto con quelli della nuova release.

Al successivo avvio, PHOTO-CAT può ricreare `.venv/` se l’ambiente locale non è più compatibile con la nuova versione.
