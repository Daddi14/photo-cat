# Risoluzione problemi

## La GUI non si apre

La configurazione grafica richiede Tkinter.

PHOTO-CAT controlla Tkinter prima di aprire la GUI e prova a gestire i casi comuni su macOS/Linux. Se il controllo fallisce, installa Tkinter per la versione Python usata oppure lascia che PHOTO-CAT usi il runtime locale di fallback.

## `.venv` è rotto dopo aver spostato la cartella

PHOTO-CAT rileva ambienti virtuali spostati o rotti e ricrea automaticamente `.venv/`.

Se necessario, chiudi PHOTO-CAT, elimina `.venv/` e avvia di nuovo il launcher.

## Un percorso Homebrew Python non esiste più

Homebrew può rimuovere vecchi percorsi framework Python durante gli aggiornamenti.

PHOTO-CAT controlla se `.venv/bin/python` può avviarsi. Se non può, l’ambiente viene ricreato prima di continuare con l’installazione delle dipendenze.

## Le dipendenze non si installano

Controlla il messaggio in console e `logs/install.log`.

Cause comuni includono:

- nessuna connessione internet durante il primo setup
- accesso di rete bloccato
- versione Python non supportata
- installazione Python incompleta
- problemi di permessi nella cartella del progetto

## Errori nei nomi delle colonne

I nomi delle colonne sono case-sensitive.

Apri il CSV catalogo o target e conferma che i nomi delle colonne configurati corrispondano esattamente agli header.

## Errori nella cartella indice

La fase di query richiede una cartella indice completa dalla fase di build.

Esegui di nuovo la fase di build se mancano file, il catalogo è cambiato o la cartella indice è stata spostata.

## Problemi con il percorso di output

Assicurati che la cartella di output configurata sia scrivibile e non sia dentro una cartella di sistema protetta.

## `photo-cat doctor` segnala file progetto mancanti dopo installazione da PyPI

Quando PHOTO-CAT è installato da PyPI, `photo-cat doctor` viene eseguito in modalità pacchetto. In questa modalità, file progetto come `config.yaml`, `VERSION`, `.venv/` e `.runtime/` non sono richiesti accanto al pacchetto installato.

Per validare una configurazione specifica, passala esplicitamente:

```bash
photo-cat doctor --config config.yaml
```

Quando `photo-cat doctor` viene eseguito da una cartella release/sorgente estratta, controlla anche i file di contesto del progetto come `config.yaml` e `VERSION`.
