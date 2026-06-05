# Risoluzione problemi

## La GUI non si apre

Su macOS/Linux, verifica che Tkinter sia disponibile. Il launcher prova a gestire automaticamente i casi più comuni.

## L’ambiente locale viene ricreato

È normale se PHOTO-CAT rileva che `.venv/` non è più riutilizzabile, per esempio dopo aver spostato la cartella del progetto o dopo un aggiornamento di Python.

## Il CSV non viene letto

Controlla che il file esista, che sia un CSV valido e che i nomi delle colonne corrispondano esattamente a quelli configurati.

## La pipeline non trova l’indice

Esegui prima la fase di build o controlla il percorso dell’indice nella configurazione.
