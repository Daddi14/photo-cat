# Configurazione

PHOTO-CAT salva la configurazione in `config.yaml`.

## Sezioni principali

Il file di configurazione contiene sezioni per:

- creazione dell’indice dei vicini
- query di contaminazione
- controllo delle fasi da eseguire
- percorsi di input e output

## Gestione percorsi del catalogo

I percorsi possono essere assoluti o relativi alla cartella del progetto.

La GUI prova a mantenere i percorsi leggibili e portabili quando possibile.

## Fase di build

La fase di build legge il catalogo, valida le colonne richieste e crea un indice dei vicini.

Le impostazioni principali includono raggio massimo, dimensione chunk, uso di Dask e salvataggio opzionale delle separazioni.

## Fase di query

La fase di query analizza target selezionati usando l’indice creato.

Le impostazioni principali includono campo di vista, limite di magnitudine e origine dei target.

## Save + run

Il pulsante `Save + run` salva `config.yaml` e avvia la pipeline con la configurazione corrente.
