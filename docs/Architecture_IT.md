<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Architettura e confini dei test

PHOTO-CAT è organizzato attorno a comportamenti pubblici stabili e a un'implementazione interna sostituibile.

## Interfacce pubbliche

Le seguenti interfacce sono considerate contratti verso gli utenti:

- `photo-cat` e i relativi sottocomandi documentati.
- I nomi delle sezioni di `config.yaml` e le impostazioni documentate.
- Il configuratore grafico.
- I file prodotti dalla costruzione dell'indice.
- I campi JSON prodotti dalla query.
- Le modalità package-install e cartella progetto di `photo-cat doctor`.

I test di regressione devono proteggere queste interfacce mentre il codice interno viene suddiviso o migliorato.

## Fasi della pipeline

La pipeline runtime ha tre confini:

1. **Configurazione**: interpreta YAML, risolve i percorsi e valida tipi e intervalli delle impostazioni.
2. **Build/index**: carica il catalogo e crea l'indice dei vicini riprendibile.
3. **Query/contaminazione**: legge l'indice e produce risultati di contaminazione per i target configurati.

`config_and_run.py` è limitato all'orchestrazione della pipeline. Stabilisce quali fasi sono abilitate e invoca i moduli build e query; non esegue direttamente calcoli scientifici.

## Strategia di test

I test sono raggruppati per scopo:

- I **test di regressione** proteggono CLI, pipeline e comportamento dei risultati pubblici.
- I **test unitari** verificano helper puri come validazione di percorsi/configurazione, conversioni di coordinate, risoluzione degli ID e calcoli di flusso.
- I **test di integrazione** usano il catalogo e i target di esempio inclusi per verificare insieme build e query.

Gli input temporanei condivisi appartengono a `tests/conftest.py`. I test devono includere una docstring quando il risultato atteso dipende da una regola scientifica, da una convenzione numerica o da un comportamento di compatibilità non ovvio.

## Indicazioni per il refactoring

Il refactoring deve prima preservare i contratti pubblici. È preferibile estrarre un helper focalizzato da una funzione ampia, aggiungere test unitari e solo dopo semplificare il chiamante. Non introdurre un design pattern solo per il suo nome: Strategy o Chain of Responsibility vanno adottati soltanto quando esistono realmente più politiche di esecuzione o validazione intercambiabili.
