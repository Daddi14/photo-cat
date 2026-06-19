# Runtime e Python

PHOTO-CAT è progettato per mantenere il runtime locale alla cartella del progetto.

## Versioni Python supportate

PHOTO-CAT può usare un’installazione Python esistente solo se è supportata e supera i controlli d’ambiente richiesti.

Versioni supportate:

- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13

Le versioni più vecchie vengono ignorate. Python 3.14 e superiori non vengono selezionati di default per ora.

## Runtime locale di fallback

Se non è disponibile un Python adatto, PHOTO-CAT usa un runtime privato sotto:

`.runtime/`

Questo evita di modificare l’installazione Python di sistema dell’utente.

## Ambiente virtuale

Le dipendenze vengono installate solo dentro:

`.venv/`

PHOTO-CAT non installa pacchetti nell’ambiente Python globale dell’utente.

## Cosa PHOTO-CAT non fa

PHOTO-CAT non:

- modifica `PATH` in modo permanente
- aggiorna il Python dell’utente
- disinstalla il Python dell’utente
- installa dipendenze nel Python di sistema
- sovrascrive un’installazione Python di lavoro esistente
- richiede agli utenti di eseguire Poetry o uv manualmente

## Rilevamento ambienti obsoleti

Se `.venv/` viene spostato, è rotto, eliminato parzialmente o punta a un runtime Python rimosso, PHOTO-CAT lo ricrea automaticamente.

`photo-cat doctor` segnala un ambiente locale non aggiornato come avviso recuperabile. I controlli automatici possono usare `photo-cat doctor --format json` e ispezionare la diagnostica `project_venv`.

Questo aiuta in casi comuni come lo spostamento della cartella del progetto o la rimozione di un vecchio percorso framework Python da parte di Homebrew su macOS.
