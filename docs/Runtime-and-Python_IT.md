# Runtime e Python

PHOTO-CAT evita di modificare il Python dell’utente o del sistema.

I launcher usano un Python esistente solo se è supportato e supera i controlli richiesti. Le versioni supportate sono Python 3.10, 3.11, 3.12 e 3.13.

Se non è disponibile un Python adatto, PHOTO-CAT usa un runtime privato nella cartella `.runtime/`.

Il pacchetto PHOTO-CAT e le dipendenze vengono installati solo nell’ambiente locale `.venv/`.

PHOTO-CAT non modifica `PATH` in modo permanente e non installa pacchetti nel Python di sistema.
