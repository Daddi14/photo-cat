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

La pipeline runtime ha cinque confini espliciti:

1. **Caricamento del documento di configurazione**: legge YAML e stabilisce la directory del file config senza creare cartelle runtime né aprire risorse scientifiche.
2. **Configurazione derivata**: applica gli override CLI a una copia profonda della mappa, lasciando invariato il documento caricato.
3. **Interpretazione e validazione runtime**: crea impostazioni tipizzate, valida file e directory e risolve percorsi nominati prima dell'esecuzione della fase.
4. **Build/index**: carica il catalogo e crea l'indice dei vicini riprendibile.
5. **Query/contaminazione**: valida i percorsi dell'indice, poi apre gli array e produce risultati di contaminazione per i target configurati.

`config_and_run.py` è limitato all'orchestrazione della pipeline. Stabilisce quali fasi sono abilitate e invoca i moduli build e query con un percorso config esplicito; non modifica la directory di lavoro del chiamante né esegue direttamente calcoli scientifici.

## Mappa delle responsabilità dei moduli

| Modulo | Responsabilità attuale | Rischio per i contratti durante il refactoring |
|---|---|---|
| `path_policy.py` | Risolve i percorsi runtime non-GUI, valida i confini del filesystem e denomina i file dell’indice/query. | Regole per percorsi relativi, contenimento degli output e layout della directory dell’indice. |
| `load_config.py` | Carica documenti YAML isolati, interpreta impostazioni tipizzate e valida separatamente gli input runtime usando la politica dei percorsi condivisa. | Chiavi di configurazione, valori predefiniti, messaggi di validazione, percorsi relativi al file config e assenza di perdita di stato tra caricamenti. |
| `cli.py` e `cli_overrides.py` | Interpretano i comandi CLI documentati, derivano config temporanee per gli override e circoscrivono lo stato d’ambiente della GUI legacy. | Nomi dei comandi, opzioni, override relativi alla directory di lavoro, stati di uscita, convenzione `ERROR:` e isolamento degli override. |
| `config_and_run.py` | Seleziona le fasi abilitate e passa un unico percorso config esplicito ai processi figli. | Ordine build-prima-query, flag delle fasi e isolamento dell’ambiente/directory di lavoro del chiamante. |
| `build_neighbors_index.py` | Carica cataloghi e crea l'indice dei vicini riutilizzabile. | Layout della directory dell'indice e convenzioni numeriche dei vicini. |
| `query_contamination_from_index.py` | Legge un indice e scrive risultati JSON di contaminazione per target. | Campi JSON, gestione degli ID target e convenzioni di flusso/separazione. |
| `doctor.py` | Riporta diagnostiche per pacchetto e progetto sorgente. | Comportamento diagnostico in modalità pacchetto installato e cartella progetto. |

Il refactoring futuro dovrebbe iniziare estraendo una sola responsabilità focalizzata da un modulo, quindi proteggendo il confine pubblico circostante con test di regressione. La politica dei percorsi è ora separata dall’esecuzione runtime non-GUI: configurazione e CLI risolvono i percorsi rispetto a una directory base esplicita, mentre la query consuma `IndexPaths` nominati e validati senza ricostruire inline i nomi dei file dell’indice.

## Confine del ciclo di vita della configurazione

Lo stato della configurazione è separato intenzionalmente dall'esecuzione runtime:

- `load_configuration_document()` legge una mappa YAML e registra la directory usata per i percorsi relativi al file config. Non crea cartelle, non apre array dell'indice e non modifica lo stato dell'ambiente di processo.
- I lettori delle sezioni restituiscono copie profonde, quindi interpretare una sezione o derivare override CLI non può modificare un caricamento successivo.
- `load_config(..., validate_runtime=False)` permette interpretazione e validazione tipizzata senza controllare file di input; la modalità runtime predefinita valida poi file richiesti e target di output prima dell'avvio.
- Gli override CLI creano un YAML temporaneo solo quando serve per mantenere l'interfaccia file-based esistente dei moduli. Il valore `PHOTO_CAT_CONFIG` del processo padre non viene modificato.
- I processi figli della pipeline ricevono la config selezionata attraverso una copia dell'ambiente. Il processo padre mantiene directory di lavoro e ambiente originali.

Questo ciclo rende deterministici i comandi ripetuti nello stesso processo Python e mantiene la creazione delle risorse dopo i confini di interpretazione e validazione.

## Confine della politica dei percorsi

La risoluzione dei percorsi è separata intenzionalmente dall’esecuzione scientifica e della pipeline:

- I percorsi scritti in `config.yaml` sono risolti rispetto alla directory che contiene quel file di configurazione.
- I percorsi CLI espliciti `--config` e gli override diretti dei percorsi CLI sono risolti rispetto alla directory di lavoro da cui viene invocato `photo-cat`.
- `path_policy.py` gestisce espansione, risoluzione assoluta, validazione di file/directory, denominazione del layout dell’indice e collocamento controllato degli output della query.
- Il modulo query valida un oggetto `IndexPaths` prima di aprire memory map o eseguire lavoro numerico.

Questo rende le regole del filesystem testabili in modo indipendente ed evita di modificare la directory di lavoro del processo soltanto per interpretare un percorso.

## Revisione delle responsabilità

La revisione v1.6.0 applica le parti pratiche di SOLID senza aggiungere pattern solo per il loro nome:

- **Responsabilità singola:** `load_config.py` ora separa caricamento del documento, interpretazione delle sezioni e validazione degli input runtime; `path_policy.py` gestisce la creazione esplicita delle directory runtime; la preparazione della query predispone percorsi validati prima dell'elaborazione numerica.
- **Direzione esplicita delle dipendenze:** il codice CLI passa un percorso config ai moduli runtime. Il codice pipeline passa tale percorso solo agli ambienti dei processi figli, invece di dipendere da una modifica dell'ambiente del processo padre.
- **Confine pubblico stabile:** build, query e diagnostica continuano a esporre gli stessi comandi documentati, chiavi di configurazione, layout dei risultati e convenzioni degli errori.
- **Responsabilità ancora concentrate:** persistenza della GUI, ciclo checkpoint/output finale della build, interpretazione target/persistenza JSON della query e controlli operativi di installer/doctor restano i prossimi candidati per lavoro isolato.

Strategy e Chain of Responsibility non sono ancora giustificati: il codice attuale ha una modalità build, una modalità query e un unico ciclo di validazione ordinato, non politiche intercambiabili.

## Mappa dei refactoring rimanenti

I seguenti candidati sono identificati per future attività mirate; non richiedono una riscrittura estesa:

| Modulo o area | Responsabilità candidata da isolare | Protezione suggerita prima della modifica |
|---|---|---|
| `configure_gui.py` | Stato UI, presentazione dei percorsi e persistenza della configurazione sono ancora strettamente collegati. | Test di regressione GUI/salvataggio config e verifica manuale dei launcher. |
| `build_neighbors_index.py` | Ciclo di resume/checkpoint e persistenza finale dei file dell’indice restano lavoro runtime procedurale. | Test di regressione del layout dell’indice e test mirati dei checkpoint. |
| `query_contamination_from_index.py` | Interpretazione degli input target e persistenza JSON possono essere ulteriormente separate dal calcolo numerico. | Test di regressione dello schema dei risultati query. |
| `doctor.py` e `install.py` | Diagnostica dell’ambiente e workflow di installazione sono intenzionalmente operativi ma estesi. | Test della diagnostica in modalità pacchetto installato e progetto sorgente. |

Usa questa mappa per selezionare una responsabilità circoscritta per release. Strategy o Chain of Responsibility rimangono non necessari finché non emergono politiche realmente intercambiabili.

## Strategia di test

I test sono raggruppati per scopo:

- I **test di regressione** (`@pytest.mark.regression`) proteggono CLI, pipeline e comportamento dei risultati pubblici.
- I **test unitari** (`@pytest.mark.unit`) verificano helper puri come validazione di percorsi/configurazione, conversioni di coordinate, risoluzione degli ID e calcoli di flusso.
- I **test di integrazione** usano il catalogo e i target di esempio inclusi per verificare insieme build e query.
- I **report di coverage** individuano i percorsi non testati; guidano le priorità ma non sostituiscono le asserzioni sul comportamento.

Gli input temporanei condivisi appartengono a `tests/conftest.py`. I confini del ciclo di vita della configurazione e dello stato di processo sono coperti da `tests/test_configuration_lifecycle.py` e `tests/test_runtime_boundaries.py`. Ogni test è classificato esplicitamente con `@pytest.mark.regression` o `@pytest.mark.unit`; la CI usa una gestione rigorosa dei marker. I test devono includere una docstring quando il risultato atteso dipende da una regola scientifica, da una convenzione numerica o da un comportamento di compatibilità non ovvio. Vedi [Workflow di sviluppo](Development_IT.md) e [Contratti pubblici](Public-Contracts_IT.md) per le regole rivolte ai contributori.

## Indicazioni per il refactoring

Il refactoring deve prima preservare i contratti pubblici. È preferibile estrarre un helper focalizzato da una funzione ampia, aggiungere test unitari e solo dopo semplificare il chiamante. Non introdurre un design pattern solo per il suo nome: Strategy o Chain of Responsibility vanno adottati soltanto quando esistono realmente più politiche di esecuzione o validazione intercambiabili.
