# Configurazione

PHOTO-CAT salva la configurazione di esecuzione nel file `config.yaml` nella cartella principale.

Il modo consigliato per modificare questo file è usare la configurazione grafica aperta da `START_WINDOWS.bat` o `START_UNIX.sh`.

## Sezioni principali

La configurazione controlla:

- percorso del catalogo di input
- percorso del file target o target manuali
- mapping delle colonne del catalogo
- cartella di output
- percorsi dell’indice dei vicini
- opzioni della fase di build
- opzioni della fase di query
- modalità di esecuzione

## Gestione percorsi del catalogo

Quando viene selezionato un CSV catalogo nella GUI, PHOTO-CAT può inizializzare percorsi collegati come file target, cartella output/indice e cartella indice per la query.

I valori restano modificabili prima dell’esecuzione.

## Fase di build

La fase di build crea un indice dei vicini dal catalogo.

Usala quando cambiano catalogo, colonne coordinate, raggio di ricerca o cartella output/indice.

## Fase di query

La fase di query legge un indice esistente e processa i target selezionati.

Usala quando l’indice esiste già e devi solo interrogare target o modificare opzioni di query.

## Save + run

`Save + run` scrive le impostazioni correnti della GUI in `config.yaml`, poi avvia la pipeline in una console separata.

La console della pipeline mostra il progresso e il percorso finale dell’output.


## Override CLI

Ogni valore in `config.yaml` può anche essere sovrascritto da riga di comando per una singola esecuzione.

Esempio:

```bash
photo-cat run --config config.yaml --field-of-view-arcsec 60 --delta-mag 4
```

Il file YAML non viene modificato permanentemente. Per tutti i flag di override disponibili e gli esempi, vedi [Uso da riga di comando](Command-line_IT.md).
