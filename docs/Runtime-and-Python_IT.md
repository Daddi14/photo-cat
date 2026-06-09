# Runtime e Python

PHOTO-CAT usa Python localmente senza modificare l’installazione Python dell’utente o del sistema.

## Versioni Python supportate

Le versioni supportate sono:

- Python 3.10
- Python 3.11
- Python 3.12
- Python 3.13

Python più vecchi vengono ignorati. Python 3.14 e superiori non sono abilitati di default in questa versione.

## Runtime locale di fallback

Se non è disponibile un Python supportato, PHOTO-CAT usa un runtime privato nella cartella `.runtime/`.

Questo runtime appartiene solo alla cartella del progetto.

## Ambiente virtuale

PHOTO-CAT installa il pacchetto e le dipendenze nell’ambiente locale `.venv/`.

Questo mantiene il progetto isolato dal Python di sistema.

## Cosa PHOTO-CAT non fa

PHOTO-CAT non:

- modifica `PATH` in modo permanente
- aggiorna il Python dell’utente
- disinstalla il Python dell’utente
- installa pacchetti nel Python di sistema
- richiede all’utente di usare Poetry o uv manualmente

## Rilevamento ambienti obsoleti

Se `.venv/` è stato creato in un vecchio percorso, punta a un Python rimosso o non è più riutilizzabile, PHOTO-CAT lo ricrea automaticamente.
