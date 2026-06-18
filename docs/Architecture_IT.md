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

## Mappa delle responsabilità dei moduli

| Modulo | Responsabilità attuale | Rischio per i contratti durante il refactoring |
|---|---|---|
| `load_config.py` | Interpreta YAML, risolve i percorsi documentati e valida dataclass di configurazione tipizzate. | Chiavi di configurazione, valori predefiniti, regole per percorsi relativi e messaggi di validazione. |
| `cli.py` e `cli_overrides.py` | Interpretano i comandi CLI documentati e creano override runtime temporanei. | Nomi dei comandi, opzioni, stati di uscita e convenzione `ERROR:`. |
| `config_and_run.py` | Seleziona e invoca le fasi della pipeline abilitate. | Ordine build-prima-query e flag delle fasi. |
| `build_neighbors_index.py` | Carica cataloghi e crea l'indice dei vicini riutilizzabile. | Layout della directory dell'indice e convenzioni numeriche dei vicini. |
| `query_contamination_from_index.py` | Legge un indice e scrive risultati JSON di contaminazione per target. | Campi JSON, gestione degli ID target e convenzioni di flusso/separazione. |
| `doctor.py` | Riporta diagnostiche per pacchetto e progetto sorgente. | Comportamento diagnostico in modalità pacchetto installato e cartella progetto. |

Il refactoring futuro dovrebbe iniziare estraendo una sola responsabilità focalizzata da un modulo, quindi proteggendo il confine pubblico circostante con test di regressione. La politica dei percorsi rimane una candidata per un'ulteriore separazione dall'esecuzione runtime quando ciò crea confini più chiari e testabili.

## Strategia di test

I test sono raggruppati per scopo:

- I **test di regressione** (`@pytest.mark.regression`) proteggono CLI, pipeline e comportamento dei risultati pubblici.
- I **test unitari** (`@pytest.mark.unit`) verificano helper puri come validazione di percorsi/configurazione, conversioni di coordinate, risoluzione degli ID e calcoli di flusso.
- I **test di integrazione** usano il catalogo e i target di esempio inclusi per verificare insieme build e query.
- I **report di coverage** individuano i percorsi non testati; guidano le priorità ma non sostituiscono le asserzioni sul comportamento.

Gli input temporanei condivisi appartengono a `tests/conftest.py`. Ogni test è classificato esplicitamente con `@pytest.mark.regression` o `@pytest.mark.unit`; la CI usa una gestione rigorosa dei marker. I test devono includere una docstring quando il risultato atteso dipende da una regola scientifica, da una convenzione numerica o da un comportamento di compatibilità non ovvio. Vedi [Workflow di sviluppo](Development_IT.md) e [Contratti pubblici](Public-Contracts_IT.md) per le regole rivolte ai contributori.

## Indicazioni per il refactoring

Il refactoring deve prima preservare i contratti pubblici. È preferibile estrarre un helper focalizzato da una funzione ampia, aggiungere test unitari e solo dopo semplificare il chiamante. Non introdurre un design pattern solo per il suo nome: Strategy o Chain of Responsibility vanno adottati soltanto quando esistono realmente più politiche di esecuzione o validazione intercambiabili.
