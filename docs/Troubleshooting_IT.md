# Risoluzione problemi

## La GUI non si apre

Su macOS/Linux, il problema può essere legato a Tkinter.

Il launcher prova a verificare Tkinter prima di aprire la GUI e mostra un messaggio più chiaro se manca il supporto grafico.

## `.venv` è rotto dopo aver spostato la cartella

PHOTO-CAT rileva quando `.venv/` punta ancora al vecchio percorso del progetto.

In questo caso, l’ambiente locale viene ricreato automaticamente.

## Un percorso Homebrew Python non esiste più

Su macOS, Homebrew può rimuovere vecchie build di Python.

Se `.venv/` punta a un framework Python non più presente, PHOTO-CAT rileva il problema e ricrea l’ambiente locale.

## Le dipendenze non si installano

Controlla la connessione internet e il log indicato nella console.

Le dipendenze vengono installate solo in `.venv/`.

## Errori nei nomi delle colonne

I nomi delle colonne sono case-sensitive.

Controlla che i nomi configurati nella GUI corrispondano esattamente all’header del CSV.

## Errori nella cartella indice

Se la fase query non trova l’indice, esegui prima la fase di build oppure controlla il percorso dell’indice in `config.yaml`.

## Problemi con il percorso di output

Assicurati che la cartella di output sia scrivibile e che il percorso non punti a una posizione protetta o inesistente.
