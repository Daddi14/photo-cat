# Download e utilizzo

## Scaricare e iniziare con PHOTO-CAT

PHOTO-CAT è distribuito come cartella di progetto con launcher per piattaforma. Gli utenti normali dovrebbero partire dalla cartella principale e non devono aprire manualmente `src/` o `scripts/`.

Per rigenerare il catalogo Gaia, eseguire la pipeline e creare i grafici coordinati dei risultati del paper, segui [Riprodurre i risultati del paper](REPRODUCE_PAPER_RESULT_IT.md).

## Avvio rapido

1. Scarica l’archivio dell’ultima release.
2. Estrailo in una normale cartella utente.
3. Avvia il launcher per il tuo sistema operativo:
   - Windows: doppio clic su `START_WINDOWS.bat`
   - macOS/Linux: apri il Terminale nella cartella ed esegui `sh START_UNIX.sh`
4. Attendi che PHOTO-CAT prepari l’ambiente locale.
5. Seleziona il catalogo CSV nella configurazione grafica.
6. Scegli inglese o italiano dal selettore della lingua.
7. Fermati con il puntatore su qualsiasi impostazione, valore, sezione o azione per leggerne il tooltip; i campi astronomici spiegano il termine e il suo effetto pratico.
8. Controlla i nomi delle colonne rilevati.
9. Scegli le opzioni di build/query necessarie.
10. Clicca `Salva e avvia la pipeline`.

## Primo avvio

Il primo avvio può richiedere alcuni minuti perché PHOTO-CAT prepara un ambiente locale e installa le dipendenze in `.venv/`.

PHOTO-CAT non installa dipendenze nel Python di sistema dell’utente. Se non è disponibile un Python adatto, usa un runtime privato sotto `.runtime/`.

## Windows

Usa:

`START_WINDOWS.bat`

Il launcher apre una console di setup, prepara runtime e ambiente locali, poi apre la configurazione grafica.

## macOS/Linux

Usa:

`sh START_UNIX.sh`

Su macOS, avviare il launcher dal Terminale evita problemi causati da file comando scaricati e bloccati da Gatekeeper.

## Esecuzione della pipeline

Dopo aver configurato l’esecuzione, clicca `Salva e avvia la pipeline` nella GUI. PHOTO-CAT apre una console della pipeline e mostra le fasi correnti, gli indicatori di progresso e il percorso di output.

Ogni fase build/query mostra una barra di avvio subito dopo l'intestazione mentre Python importa il modulo e prepara il primo avanzamento dettagliato. La barra di avvio lascia spazio a quella della fase non appena il processo figlio produce output.

Ogni comando avviato da un pannello della GUI riceve anche una riga animata nella console Output degli strumenti. Mostra subito nome del comando e tempo trascorso, poi resta come stato completato o non riuscito anche quando il comando non produce messaggi intermedi.

Le percentuali determinate rappresentano sempre elementi, righe, blocchi o target realmente completati. Le operazioni per cui le librerie non espongono un totale affidabile usano una barra indeterminata in movimento con attività corrente e tempo trascorso, senza inventare una percentuale. La creazione dell'ambiente elenca le fasi effettive e l'installazione delle dipendenze indica il pacchetto in fase di download o installazione.

## Interfaccia a riga di comando

Dopo l’installazione del pacchetto, PHOTO-CAT fornisce anche una CLI unificata.

```bash
photo-cat configure
photo-cat run --config config.yaml
photo-cat build-index --config config.yaml
photo-cat query --config config.yaml
photo-cat doctor
```

Usa la CLI per esecuzioni da script, macchine remote, cluster o workflow in cui non è pratico aprire la GUI. Per il riferimento completo degli override, vedi [Uso da riga di comando](Command-line_IT.md).

`photo-cat doctor` può essere usato dopo una normale installazione del pacchetto per controllare Python, Tkinter, PHOTO-CAT e le dipendenze richieste. Quando viene eseguito dentro una cartella progetto/release, controlla anche il contesto del progetto come `config.yaml` e `VERSION`.

## Aggiornare PHOTO-CAT

Per aggiornare un’installazione esistente, sostituisci i file del progetto con quelli della nuova release mantenendo i tuoi dati e le cartelle di output.

PHOTO-CAT può ricreare `.venv/` al prossimo avvio se l’ambiente esistente è obsoleto, rotto o legato a un vecchio percorso del progetto.
