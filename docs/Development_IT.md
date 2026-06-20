<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Workflow di sviluppo

Questa guida è destinata ai contributori che lavorano da un checkout dei sorgenti di PHOTO-CAT.

Per il normale utilizzo desktop, usa i launcher nella root. Il workflow di sviluppo è pensato per modifiche al codice, revisioni, controlli automatizzati e debugging riproducibile.

## Versioni Python supportate

Il pacchetto supporta Python dalla 3.10 alla 3.13.

Crea un ambiente virtuale isolato nella repository:

```bash
python -m venv .venv
```

Attivalo:

```bash
# Prompt dei comandi Windows
.venv\Scripts\activate.bat

# PowerShell Windows
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Installa il pacchetto in modalità modificabile e gli strumenti di sviluppo:

```bash
python -m pip install --upgrade pip
python -m pip install -e .
python -m pip install pytest pytest-cov build
```

## Controlli quotidiani

Esegui l'intera suite:

```bash
pytest
```

Esegui solo i test che proteggono il comportamento documentato e visibile agli utenti:

```bash
pytest -m regression
```

Esegui i test isolati di helper e validazione:

```bash
pytest -m unit
```

Esegui la coverage localmente:

```bash
pytest --cov=photo_cat --cov-report=term-missing
```

La CI impone marker di test rigorosi e una baseline di coverage del 78%. La baseline protegge dalle regressioni, ma non significa che tutti i percorsi abbiano la stessa importanza scientifica. Le nuove modifiche devono aggiungere asserzioni significative, non test creati solo per aumentare la percentuale.

## Contratti pubblici e tipi di test

Leggi [Contratti pubblici](Public-Contracts_IT.md) prima di modificare un comando, una chiave di configurazione, il layout dell'indice o un campo del risultato della query.

- Usa `@pytest.mark.regression` per i test che proteggono il comportamento documentato di CLI, pipeline, indice o output.
- Usa `@pytest.mark.unit` per helper isolati e confini di validazione che possono essere riorganizzati internamente.
- Ogni test marcato deve avere un docstring conciso quando il suo intento tecnico, scientifico, numerico o di compatibilità non è evidente dal nome.
- Mantieni i test centrati sul comportamento osservabile. Non legare i test di regressione alla struttura di helper privati che un refactoring può sostituire intenzionalmente.

I dati di test condivisi e gli helper per configurazioni temporanee appartengono a `tests/conftest.py`. Le regole dei percorsi runtime sono coperte da `tests/test_path_policy.py`; l'isolamento della configurazione e dello stato di processo è coperto da `tests/test_configuration_lifecycle.py` e `tests/test_runtime_boundaries.py`. Preserva la distinzione tra percorsi relativi al file config e percorsi CLI relativi alla directory di lavoro.

Quando modifichi il flusso di configurazione, verifica che l'interpretazione non crei cartelle di output, che gli override CLI non modifichino la config base e che le fasi figlie della pipeline ricevano la configurazione tramite un ambiente copiato esplicito, non tramite una modifica del processo padre.

## Verificare una modifica prima di aprire una pull request

Dalla root della repository, esegui:

```bash
python -m py_compile src/photo_cat/*.py
pytest
pytest --cov=photo_cat --cov-report=term-missing
python -m build
photo-cat --version
photo-cat doctor
```

Su macOS/Linux, controlla anche la sintassi dei launcher:

```bash
bash -n START_UNIX.sh scripts/*.sh
```

Per modifiche a CLI, configurazione, build/indice o query:

1. Esegui i test di regressione con `pytest -m regression`.
2. Esegui il workflow di esempio end-to-end con `pytest tests/test_pipeline_sample.py`.
3. Aggiorna la documentazione utente inglese e italiana quando il comportamento cambia.
4. Verifica che non siano stati preparati file generati:

```bash
git status --short
git diff --check
```

Non fare commit di `.venv/`, `.runtime/`, artefatti di build, indici generati, log, output, `__pycache__/` o file `*.pyc`.

## Aspettative per le pull request

Mantieni le pull request focalizzate. Spiega il comportamento pubblico coinvolto, i test aggiunti o aggiornati e l'eventuale lavoro successivo ancora necessario.

Il template della pull request include i controlli della repository. Usalo come checklist di revisione, non limitarti a spuntare le caselle automaticamente.

## Documentazione correlata

- [Contribuire](../CONTRIBUTING.md)
- [Architettura e confini dei test](Architecture_IT.md)
- [Contratti pubblici](Public-Contracts_IT.md)
- [Uso da riga di comando](Command-line_IT.md)
- [Pubblicare PHOTO-CAT](PUBLISHING_IT.md)
