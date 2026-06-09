# Pipeline e output

PHOTO-CAT può eseguire due fasi principali: creazione dell’indice e query di contaminazione.

## Fase 1: creazione indice dei vicini

La fase di build legge il catalogo fotometrico e crea un indice dei vicini entro il raggio massimo configurato.

L’indice viene salvato nella cartella di output configurata e viene riutilizzato dalla fase di query.

## Fase 2: query contaminazione

La fase di query legge l’indice, seleziona i target e calcola le sorgenti vicine che rispettano i limiti di campo di vista e magnitudine.

## Output JSON

La fase di query produce un file JSON con una voce per ogni target processato.

Ogni voce contiene:

- dati del target
- frazione di flusso extra
- numero di contaminanti
- lista delle sorgenti contaminanti qualificate

## Output console

La console mostra fasi, progressi, percorsi dei risultati e riepiloghi finali in formato leggibile.
