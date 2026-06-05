# Pipeline e output

PHOTO-CAT può eseguire due fasi principali.

## Creazione indice

La fase di build crea un indice dei vicini dal catalogo fotometrico.

## Query contaminazione

La fase di query analizza i target selezionati e produce un file JSON con:

- dati del target
- frazione di flusso extra
- numero di contaminanti
- lista delle sorgenti vicine qualificate
