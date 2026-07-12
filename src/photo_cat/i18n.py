# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Runtime English/Italian localization for user-visible PHOTO-CAT text."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # The dependency installer must work before PyYAML exists.
    yaml = None


SUPPORTED_LANGUAGES = {"en": "English", "it": "Italiano"}
LANGUAGE_ENVIRONMENT = "PHOTO_CAT_LANGUAGE"
_language = "it" if os.environ.get(LANGUAGE_ENVIRONMENT, "").lower().startswith("it") else "en"


ITALIAN: dict[str, str] = {
    # Common actions and interface structure.
    "Language": "Lingua",
    "Configurator": "Configuratore",
    "options": "opzioni",
    "usage:": "uso:",
    "positional arguments": "argomenti posizionali",
    "show this help message and exit": "mostra questo messaggio di aiuto ed esce",
    "language used for help, messages, errors, and console output": "lingua usata per aiuto, messaggi, errori e output della console",
    "PHOTO-CAT catalogue-level contamination risk-assessment and target-screening tools.":
        "Strumenti PHOTO-CAT per valutare il rischio di contaminazione da catalogo e selezionare i target.",
    "English": "English",
    "Italiano": "Italiano",
    "Help": "Aiuto",
    "ERROR": "ERRORE",
    "WARN": "AVVISO",
    "working": "in corso",
    "done": "completato",
    "Clear": "Pulisci",
    "Browse...": "Sfoglia...",
    "Add file...": "Aggiungi file...",
    "Select catalog CSV": "Seleziona il CSV del catalogo",
    "Select targets CSV": "Seleziona il CSV dei target",
    "Select bandpass profile YAML": "Seleziona il profilo YAML della banda",
    "Select radial weight CSV": "Seleziona il CSV dei pesi radiali",
    "Select output/index folder": "Seleziona la cartella output/indice",
    "Select existing index folder": "Seleziona la cartella di un indice esistente",
    "CSV files": "File CSV",
    "JSON files": "File JSON",
    "YAML files": "File YAML",
    "All files": "Tutti i file",
    "Run": "Esegui",
    "Run diagnostics": "Esegui diagnostica",
    "Load example config": "Carica configurazione di esempio",
    "Save config.yaml": "Salva config.yaml",
    "Save + run pipeline": "Salva e avvia la pipeline",
    "Switch to light mode": "Passa al tema chiaro",
    "Switch to dark mode": "Passa al tema scuro",
    "Configure pipeline": "Configura pipeline",
    "Results": "Risultati",
    "Catalogue": "Catalogo",
    "Benchmark": "Benchmark",
    "Diagnostics": "Diagnostica",
    "Files & columns": "File e colonne",
    "Search settings": "Impostazioni di ricerca",
    "Run options": "Opzioni di esecuzione",
    "Summarize": "Riassumi",
    "Screen / rank": "Filtra / classifica",
    "Plot (SVG)": "Grafico (SVG)",
    "Publication plots": "Grafici da pubblicazione",
    "Report": "Report",
    "Export": "Esporta",
    "Validate results": "Valida risultati",
    "Provenance": "Provenienza",
    "Merge bright stars": "Unisci stelle brillanti",
    "Benchmark table": "Tabella benchmark",
    "Reproduce": "Riproduci",
    "Doctor": "Diagnostica ambiente",
    "Tool output": "Output degli strumenti",
    "Output from Results / Catalogue / Benchmark / Diagnostics commands appears here.":
        "Qui appare l'output dei comandi Risultati / Catalogo / Benchmark / Diagnostica.",
    "Photometric Contamination Analyzer Tool - configure the pipeline and run every command.":
        "Strumento di analisi della contaminazione fotometrica - configura la pipeline ed esegui ogni comando.",

    # Pipeline configuration panels.
    "Files and columns": "File e colonne",
    "Catalog CSV": "CSV del catalogo",
    "Catalog column names": "Nomi delle colonne del catalogo",
    "Catalog Source ID column": "Colonna ID sorgente del catalogo",
    "Catalog RA column": "Colonna AR del catalogo",
    "Catalog Dec column": "Colonna Dec del catalogo",
    "Catalog magnitude column": "Colonna magnitudine del catalogo",
    "Magnitude bands (optional extra bands)": "Bande di magnitudine (bande aggiuntive opzionali)",
    "Targets CSV": "CSV dei target",
    "Targets column name": "Nome della colonna dei target",
    "Targets Source ID column": "Colonna ID sorgente dei target",
    "Output/index folder": "Cartella output/indice",
    "Query index folder": "Cartella indice per la query",
    "Manual targets": "Target manuali",
    "Use manual list": "Usa elenco manuale",
    "Max build radius, arcsec": "Raggio massimo di costruzione, arcsec",
    "Query aperture radius, arcsec": "Raggio dell'apertura di query, arcsec",
    "Outer influence radius, arcsec": "Raggio esterno di influenza, arcsec",
    "Delta magnitude": "Differenza di magnitudine",
    "Contamination bands (comma-separated, or all)": "Bande di contaminazione (separate da virgole, oppure all)",
    "Bandpass profile YAML (optional)": "Profilo YAML della banda (opzionale)",
    "Contamination weighting model": "Modello di pesatura della contaminazione",
    "Gaussian FWHM, arcsec": "FWHM gaussiana, arcsec",
    "Radial weight CSV": "CSV dei pesi radiali",
    "Advanced performance settings": "Impostazioni avanzate delle prestazioni",
    "Enable advanced settings": "Abilita impostazioni avanzate",
    "Chunk size": "Dimensione del blocco",
    "Buffer flush / checkpoint every N chunks": "Salvataggio buffer / checkpoint ogni N blocchi",
    "Options": "Opzioni",
    "Use Dask for very large CSV files": "Usa Dask per file CSV molto grandi",
    "Store neighbor separations on disk": "Salva su disco le separazioni dei vicini",
    "Run build step": "Esegui la fase di costruzione",
    "Run query step": "Esegui la fase di query",
    "Include missing target rows in results": "Includi nei risultati le righe dei target mancanti",
    "Replace running pipeline when Save + run is clicked": "Sostituisci la pipeline attiva quando si usa Salva + avvia",
    "Quick help": "Guida rapida",

    # Tool panels and fields.
    "Summarize results": "Riassumi risultati",
    "Screen / rank targets": "Filtra / classifica target",
    "Plot (SVG / matplotlib)": "Grafico (SVG / matplotlib)",
    "Catalogue provenance": "Provenienza del catalogo",
    "Benchmark pipeline": "Benchmark della pipeline",
    "Doctor diagnostics": "Diagnostica dell'ambiente",
    "Model mode": "Modalità del modello",
    "Capture provenance metadata for a catalogue CSV.": "Raccoglie metadata di provenienza per un catalogo CSV.",
    "Compare PHOTO-CAT predictions with an external reference contamination table.":
        "Confronta le previsioni PHOTO-CAT con una tabella esterna di contaminazione di riferimento.",
    "Export target-result rows to CSV or Parquet.": "Esporta le righe dei risultati in CSV o Parquet.",
    "Generate contaminant-count and separation distributions, and the RA/Dec contamination sky map.":
        "Genera distribuzioni dei conteggi e delle separazioni e la mappa di contaminazione AR/Dec.",
    "Generate reproducible summaries, plots, reports, and a manifest from configs and/or result JSONs.":
        "Genera riassunti, grafici, report e un manifest riproducibili da configurazioni e/o JSON dei risultati.",
    "Merge a Gaia-like base catalogue with a supplemental bright-star table.":
        "Unisce un catalogo di base in stile Gaia con una tabella supplementare di stelle brillanti.",
    "Rank targets by a contamination metric and assign accept / review / reject decisions.":
        "Classifica i target tramite una metrica di contaminazione e assegna decisioni accetta / revisiona / respingi.",
    "Render one or more benchmark JSON captures as a Markdown or CSV table.":
        "Converte uno o più benchmark JSON in una tabella Markdown o CSV.",
    "Run environment and configuration diagnostic checks.": "Esegue controlli diagnostici di ambiente e configurazione.",
    "Summarize a PHOTO-CAT query result JSON as text, JSON, or CSV.":
        "Riassume un JSON di risultati PHOTO-CAT come testo, JSON o CSV.",
    "Write a plot from a PHOTO-CAT query result JSON.": "Genera un grafico da un JSON di risultati PHOTO-CAT.",
    "Write an HTML or Markdown report from a PHOTO-CAT query result JSON.":
        "Genera un report HTML o Markdown da un JSON di risultati PHOTO-CAT.",
    "Output data file (path)": "File dati di output (percorso)",
    "Output image file (path; auto-named next to the result if blank)":
        "File immagine di output (percorso; nome automatico se vuoto)",
    "Output report file (path; auto-named next to the result if blank)":
        "File report di output (percorso; nome automatico se vuoto)",
    "Output summary file (optional; prints to console if blank)":
        "File di riepilogo (opzionale; stampa in console se vuoto)",
    "Default Gaia-like names are pre-filled. Change them only if your CSV headers are different. The names must match the catalog CSV exactly, including uppercase/lowercase.":
        "I nomi predefiniti in stile Gaia sono già compilati. Modificali solo se le intestazioni CSV sono diverse; devono corrispondere esattamente, incluse maiuscole e minuscole.",
    "Default target column is source_id. Change it only if your targets CSV uses another header. This is case-sensitive. Manual targets ignore this field.":
        "La colonna target predefinita è source_id. Modificala solo se il CSV usa un'altra intestazione. Maiuscole e minuscole sono distinte; i target manuali ignorano il campo.",
    "Enabled: the previous pipeline window opened by this GUI is closed before a new run starts. Disabled: each Save + run opens a separate pipeline window.":
        "Abilitato: la finestra della pipeline precedente viene chiusa prima di una nuova esecuzione. Disabilitato: ogni avvio apre una finestra separata.",
    "Leave these locked unless you know what you are doing. Wrong values can make the tool slower, use too much RAM, write too often to disk, or make long runs harder to resume safely.":
        "Lasciale bloccate se non conosci gli effetti. Valori errati possono rallentare il programma, consumare troppa RAM o rendere difficile riprendere esecuzioni lunghe.",
    "One band=catalog_column per line, for example gaia_bp=phot_bp_mean_mag. gaia_g is always mapped to the catalog magnitude column above. Extra bands can then be requested in Search settings > Contamination bands.":
        "Inserisci una riga banda=colonna_catalogo, per esempio gaia_bp=phot_bp_mean_mag. gaia_g usa sempre la colonna magnitudine principale. Le bande aggiuntive si selezionano nelle impostazioni di ricerca.",
    "Optional. Leave Targets CSV empty/null to use this source_id list instead. Use one source_id per line, or separate them with commas.":
        "Opzionale. Lascia vuoto il CSV dei target per usare questo elenco. Inserisci un source_id per riga oppure separali con virgole.",
    "The aperture radius defines the extraction/screening circle. The influence radius can be larger when a weighted PSF model should include leakage from nearby sources outside that aperture. Both must be equal to or smaller than the max build radius.":
        "Il raggio di apertura definisce il cerchio di misura. Il raggio di influenza può essere maggiore per includere luce di sorgenti esterne tramite un modello PSF pesato. Entrambi devono rientrare nel raggio massimo costruito.",
    "top_hat keeps the historical catalogue/aperture flux estimate. gaussian_psf and gaussian_aperture need a Gaussian FWHM. radial_weight needs a CSV of sep_arcsec,weight.":
        "top_hat mantiene la stima storica catalogo/apertura. gaussian_psf e gaussian_aperture richiedono una FWHM gaussiana. radial_weight richiede un CSV sep_arcsec,weight.",
    "Run selected pipeline stages using the current config and write benchmark metadata JSON. Uses the config.yaml saved by this GUI unless you pick another config file.":
        "Esegue le fasi selezionate con la configurazione corrente e salva un benchmark JSON. Usa il config.yaml della GUI salvo scelta di un altro file.",
    "Recommended workflow:\n1. Select Catalog CSV in Files & columns.\n2. Check that Targets CSV and output folders were auto-filled correctly.\n3. Leave the Gaia-like column names unchanged unless your CSV uses different headers.\n4. Click Save + run pipeline.\n5. Use the Results and Catalogue panels on the output JSON afterwards.":
        "Procedura consigliata:\n1. Seleziona il CSV del catalogo in File e colonne.\n2. Controlla il CSV target e le cartelle compilate automaticamente.\n3. Mantieni i nomi Gaia se il CSV non usa intestazioni diverse.\n4. Premi Salva e avvia la pipeline.\n5. Usa poi gli strumenti Risultati e Catalogo sul JSON prodotto.",
    "Result JSON": "JSON dei risultati",
    "Result JSON files": "File JSON dei risultati",
    "Reference CSV": "CSV di riferimento",
    "Config file": "File di configurazione",
    "Config file (optional)": "File di configurazione (opzionale)",
    "Config files": "File di configurazione",
    "Format": "Formato",
    "Kind": "Tipo",
    "Backend": "Backend grafico",
    "Metric": "Metrica",
    "Accept max percent": "Percentuale massima per accettare",
    "Review max percent": "Percentuale massima da revisionare",
    "Threshold percent (optional)": "Percentuale di soglia (opzionale)",
    "Source ID column": "Colonna ID sorgente",
    "Reference column": "Colonna di riferimento",
    "RA column": "Colonna AR",
    "Dec column": "Colonna Dec",
    "Magnitude column": "Colonna magnitudine",
    "Aperture, arcsec": "Apertura, arcsec",
    "Output directory": "Cartella di output",
    "DPI": "DPI",
    "ADQL file (optional)": "File ADQL (opzionale)",
    "Base catalog CSV": "CSV del catalogo di base",
    "Bright-star catalog CSV": "CSV del catalogo di stelle brillanti",
    "Prefer on duplicates": "Preferenza in caso di duplicati",
    "Benchmark JSON files": "File JSON di benchmark",
    "Run build stage": "Esegui fase di costruzione",
    "Run query stage": "Esegui fase di query",
    "Run each config before collecting results": "Esegui ogni configurazione prima di raccogliere i risultati",
    "Output (JSON)": "Output (JSON)",
    "Output (stats JSON)": "Output (statistiche JSON)",
    "Output (merged CSV)": "Output (CSV unito)",
    "Output screening file (path)": "File di screening di output (percorso)",
    "Output table file (path)": "File tabella di output (percorso)",
    "Provenance output (optional)": "Output di provenienza (opzionale)",
    "Matched residuals CSV file (optional)": "File CSV dei residui abbinati (opzionale)",

    # Dialogs and status output.
    "Config error": "Errore di configurazione",
    "Invalid configuration": "Configurazione non valida",
    "Invalid values": "Valori non validi",
    "Missing value": "Valore mancante",
    "Missing catalog": "Catalogo mancante",
    "Missing output folder": "Cartella di output mancante",
    "Missing index folder": "Cartella indice mancante",
    "Save failed": "Salvataggio non riuscito",
    "Saved": "Salvato",
    "Run failed": "Avvio non riuscito",
    "Save and run": "Salva e avvia",
    "Are you sure you want to save the current configuration and run the pipeline?":
        "Vuoi salvare la configurazione corrente e avviare la pipeline?",
    "Column name mismatch": "Nome della colonna non corrispondente",
    "Advanced settings warning": "Avviso sulle impostazioni avanzate",
    "Index folder not ready": "Cartella dell'indice non pronta",
    "Influence radius is larger than build radius": "Il raggio di influenza supera il raggio di costruzione",
    "Unknown contamination band": "Banda di contaminazione sconosciuta",
    "Select the catalog CSV file.": "Seleziona il file CSV del catalogo.",
    "Choose an output/index folder.": "Scegli una cartella di output/indice.",
    "Choose a query index folder.": "Scegli una cartella indice per la query.",
    "config.yaml was saved successfully.": "config.yaml è stato salvato correttamente.",
    "CSV file not found": "File CSV non trovato",
    "Output folder problem": "Problema con la cartella di output",
    "Could not read CSV header": "Impossibile leggere l'intestazione CSV",
    "Invalid Gaussian FWHM": "FWHM gaussiana non valida",
    "Invalid magnitude bands": "Bande di magnitudine non valide",
    "Missing targets column name": "Nome della colonna target mancante",
    "Missing targets": "Target mancanti",
    "Virtual environment missing": "Ambiente virtuale mancante",
    "Could not read config.yaml.": "Impossibile leggere config.yaml.",
    "The GUI will load default values.": "La GUI caricherà i valori predefiniti.",
    "These settings are for performance tuning only.": "Queste impostazioni servono solo a regolare le prestazioni.",
    "Bad values can make the tool slower, increase RAM usage, write too often to disk, or make long runs harder to resume safely.":
        "Valori errati possono rallentare il programma, aumentare l'uso della RAM, scrivere troppo spesso su disco o rendere difficile riprendere in sicurezza le esecuzioni lunghe.",
    "Enable advanced settings anyway?": "Abilitare comunque le impostazioni avanzate?",
    "The CSV file was not found:": "Il file CSV non è stato trovato:",
    "Could not read the CSV header.": "Impossibile leggere l'intestazione del CSV.",
    "PHOTO-CAT could not create or access the output/index folder.":
        "PHOTO-CAT non ha potuto creare o accedere alla cartella output/indice.",
    "Folder:": "Cartella:",
    "Error:": "Errore:",
    "Choose a normal writable folder, for example inside Downloads or Documents.":
        "Scegli una normale cartella scrivibile, per esempio dentro Download o Documenti.",
    "The selected Query index folder does not contain a complete PHOTO-CAT index.":
        "La cartella indice della query selezionata non contiene un indice PHOTO-CAT completo.",
    "Missing files:": "File mancanti:",
    "Enable the build step, or select the output folder from a previous successful build.":
        "Abilita la fase di costruzione oppure seleziona la cartella di output di una costruzione precedente completata.",
    "Radius, delta magnitude, chunk size, and checkpoint interval must be numbers.":
        "Raggio, differenza di magnitudine, dimensione del blocco e intervallo del checkpoint devono essere numeri.",
    "Gaussian FWHM must be a number.": "La FWHM gaussiana deve essere un numero.",
    "The outer influence radius is larger than the build radius.":
        "Il raggio esterno di influenza è maggiore del raggio di costruzione.",
    "The query cannot use neighbours that were not included in the built index.":
        "La query non può usare vicini non inclusi nell'indice costruito.",
    "Save anyway?": "Salvare comunque?",
    "These contamination bands are not defined in Files & columns > Magnitude bands:":
        "Queste bande di contaminazione non sono definite in File e colonne > Bande di magnitudine:",
    "Add a band=catalog_column line for each, or use gaia_g / all.":
        "Aggiungi una riga banda=colonna_catalogo per ciascuna oppure usa gaia_g / all.",
    "Targets Source ID column cannot be empty. Use source_id unless your targets CSV uses a different header.":
        "La colonna ID sorgente dei target non può essere vuota. Usa source_id, salvo che il CSV dei target abbia un'intestazione diversa.",
    "Select a Targets CSV file, or leave Targets CSV empty and add at least one source_id in Manual targets.":
        "Seleziona un CSV dei target oppure lascialo vuoto e aggiungi almeno un source_id nei Target manuali.",
    "The local virtual environment was not found.": "L'ambiente virtuale locale non è stato trovato.",
    "Run START_WINDOWS.bat first so it can create the local virtual environment.":
        "Esegui prima START_WINDOWS.bat per creare l'ambiente virtuale locale.",
    "Interrupted by user.": "Interrotto dall'utente.",
    "PHOTO-CAT pipeline is complete.": "La pipeline PHOTO-CAT è terminata.",
    "Check the output folder for results.": "Controlla la cartella di output per i risultati.",
    "PHOTO-CAT environment check": "Controllo dell'ambiente PHOTO-CAT",
    "PHOTO-CAT environment looks ready.": "L'ambiente PHOTO-CAT sembra pronto.",
    "PHOTO-CAT environment check found issues.": "Il controllo dell'ambiente PHOTO-CAT ha rilevato problemi.",
    "Review the failed checks above. If running from a release folder, run START_WINDOWS.bat or START_UNIX.sh again to repair the local environment.":
        "Controlla le verifiche non riuscite qui sopra. Se usi una cartella di rilascio, esegui di nuovo START_WINDOWS.bat o START_UNIX.sh per riparare l'ambiente locale.",
    "PHOTO-CAT result summary": "Riepilogo dei risultati PHOTO-CAT",
    "Targets: {value}": "Target: {value}",
    "With selected contaminants: {value}": "Con contaminanti selezionati: {value}",
    "Without selected contaminants: {value}": "Senza contaminanti selezionati: {value}",
    "Selected contaminants: {value}": "Contaminanti selezionati: {value}",
    "Neighbours in radius: {value}": "Vicini entro il raggio: {value}",
    "Neighbours outside aperture: {value}": "Vicini esterni all'apertura: {value}",
    "Selected flux % mean/median/max: {value}": "Flusso selezionato % media/mediana/massimo: {value}",
    "All-neighbour flux % mean/median/max: {value}": "Flusso di tutti i vicini % media/mediana/massimo: {value}",
    "Outside-aperture flux % mean/median/max: {value}": "Flusso esterno all'apertura % media/mediana/massimo: {value}",
    "Total weighted flux % mean/median/max: {value}": "Flusso totale pesato % media/mediana/massimo: {value}",
    "Contaminants per target mean/median/max: {value}": "Contaminanti per target media/mediana/massimo: {value}",
    "Transformed total weighted flux % mean/median/max: {value}":
        "Flusso totale pesato trasformato % media/mediana/massimo: {value}",
    "Number of contaminants": "Numero di contaminanti",
    "Number of Stars": "Numero di stelle",
    "Number of targets": "Numero di target",
    "Separation (arcsec)": "Separazione (arcsec)",
    "Contaminants": "Contaminanti",
    "Targets": "Target",
    "Target magnitude": "Magnitudine del target",
    "Selected flux fraction (%)": "Frazione di flusso selezionata (%)",
    "Flux fraction (%)": "Frazione di flusso (%)",
    "Contaminant flux / target flux (%)": "Flusso contaminante / flusso target (%)",
    "Distribution of the number of contaminating sources per target":
        "Distribuzione del numero di sorgenti contaminanti per target",
    "Selected flux fraction": "Frazione di flusso selezionata",
    "Distribution of angular separations": "Distribuzione delle separazioni angolari",
    "Contaminant flux ratio vs separation": "Rapporto di flusso contaminante rispetto alla separazione",
    "Target contamination vs magnitude": "Contaminazione del target rispetto alla magnitudine",
    "Sky map of stellar contamination": "Mappa celeste della contaminazione stellare",
    "0 contaminants": "0 contaminanti",
    "1–3 contaminants": "1–3 contaminanti",
    ">3 contaminants": ">3 contaminanti",
    "RA [deg]": "AR [gradi]",
    "Dec [deg]": "Dec [gradi]",
    "Build neighbour index": "Costruzione dell'indice dei vicini",
    "Query contamination": "Calcolo della contaminazione",
    "Completed: {activity}": "Completato: {activity}",
    "Version": "Versione",
    "Project folder": "Cartella del progetto",
    "Configuration": "Configurazione",
    "PHOTO-CAT - Pipeline": "PHOTO-CAT - Pipeline",
    "Both run_build and run_query are false. Nothing to do.":
        "run_build e run_query sono entrambi disattivati. Non c'è nulla da eseguire.",
    "Failed to load execution configuration.": "Impossibile caricare la configurazione di esecuzione.",
    "[finished with exit code {code}]": "[terminato con codice di uscita {code}]",
    "[error] {error}": "[errore] {error}",
    "PHOTO-CAT configuration": "Configurazione PHOTO-CAT",
    "You can edit this file manually, or run the starter for your operating system and use the GUI.":
        "Puoi modificare questo file manualmente oppure avviare il launcher del sistema operativo e usare la GUI.",
    "Selecting Catalog CSV in the GUI auto-fills Targets CSV and the output/index folders.":
        "La selezione del CSV del catalogo nella GUI compila automaticamente il CSV dei target e le cartelle output/indice.",
    "To use manual source_id targets, set TARGETS_INPUT to null and list IDs under targets.":
        "Per usare target source_id manuali, imposta TARGETS_INPUT a null ed elenca gli ID sotto targets.",
    "Default column names are Gaia-like. Column names are case-sensitive: ra != RA.":
        "I nomi predefiniti delle colonne seguono Gaia. Maiuscole e minuscole sono distinte: ra != RA.",
    "Change them in the GUI only if your CSV headers differ.":
        "Modificali nella GUI solo se le intestazioni del CSV sono diverse.",
    "Virtual environment": "Ambiente virtuale",
    "Installation log": "Log di installazione",
    "Detailed install log": "Log dettagliato di installazione",
    "PHOTO-CAT - dependency setup": "PHOTO-CAT - configurazione delle dipendenze",
    "Prepare local environment": "Preparazione dell'ambiente locale",
    "Verify installation tools": "Verifica degli strumenti di installazione",
    "Verify PHOTO-CAT package": "Verifica del pacchetto PHOTO-CAT",
    "Install PHOTO-CAT package": "Installazione del pacchetto PHOTO-CAT",
    "Virtual environment created.": "Ambiente virtuale creato.",
    "Virtual environment already exists. Reusing it.": "L'ambiente virtuale esiste già e verrà riutilizzato.",
    "Installation tools are ready.": "Gli strumenti di installazione sono pronti.",
    "PHOTO-CAT and its dependencies are already available.": "PHOTO-CAT e le sue dipendenze sono già disponibili.",
    "PHOTO-CAT package is ready.": "Il pacchetto PHOTO-CAT è pronto.",
    "Installing PHOTO-CAT and dependencies from pyproject.toml.":
        "Installazione di PHOTO-CAT e delle dipendenze definite in pyproject.toml.",
    "PHOTO-CAT package installed successfully.": "Pacchetto PHOTO-CAT installato correttamente.",
    "PHOTO-CAT setup is complete.": "La configurazione di PHOTO-CAT è terminata.",
    "The local environment is ready to use.": "L'ambiente locale è pronto per l'uso.",
    "creating environment folders": "creazione delle cartelle dell'ambiente",
    "writing pyvenv.cfg": "scrittura di pyvenv.cfg",
    "installing the Python executable": "installazione dell'eseguibile Python",
    "bootstrapping pip": "inizializzazione di pip",
    "installing activation scripts": "installazione degli script di attivazione",
    "finalizing the virtual environment": "completamento dell'ambiente virtuale",
    "checking photo-cat and dependency consistency": "verifica della coerenza di photo-cat e delle dipendenze",
    "removing the old virtual environment": "rimozione del vecchio ambiente virtuale",
    "Install Python from https://www.python.org/downloads/ and run this again.":
        "Installa Python da https://www.python.org/downloads/ ed esegui di nuovo il programma.",
    "On Linux, you may need to install the python3-venv package first.":
        "Su Linux potrebbe essere necessario installare prima il pacchetto python3-venv.",
    "Delete the .venv folder and run the installer again.":
        "Elimina la cartella .venv ed esegui di nuovo l'installer.",
    "Last log lines:": "Ultime righe del log:",
    "Bandpass transformation coefficients cannot contain null values.":
        "I coefficienti della trasformazione di banda non possono contenere valori null.",
    "validity.base_magnitude_min cannot exceed validity.base_magnitude_max.":
        "validity.base_magnitude_min non può superare validity.base_magnitude_max.",
    "validity.color_min cannot exceed validity.color_max.":
        "validity.color_min non può superare validity.color_max.",
    "Benchmark must run at least one stage.": "Il benchmark deve eseguire almeno una fase.",
    " - KDTree: built safely in memory": " - KDTree: costruito in modo sicuro in memoria",
    "Checkpoint contains all neighbour blocks; finalizing index outputs.":
        "Il checkpoint contiene tutti i blocchi dei vicini; completamento degli output dell'indice.",
    "Ignoring a stale checkpoint created from different build inputs.":
        "Il checkpoint obsoleto, creato con input di costruzione diversi, verrà ignorato.",
    "Resume checkpoint does not match its catalog dimensions or binary progress. Remove it to start a clean rebuild.":
        "Il checkpoint di ripristino non corrisponde alle dimensioni del catalogo o al progresso binario. Rimuovilo per ricostruire da zero.",
    "Expected comma-separated band=column entries.": "Sono richieste voci banda=colonna separate da virgole.",
    "The CSV file is empty.": "Il file CSV è vuoto.",
    "The selected index is not marked complete. Resume or rebuild it first.":
        "L'indice selezionato non risulta completo. Riprendine o ricostruiscine prima la creazione.",
    "special_ids.npz does not match the completed index manifest.":
        "special_ids.npz non corrisponde al manifest dell'indice completato.",
    "special_ids.npz is unsafe or malformed. Rebuild this legacy index before querying it.":
        "special_ids.npz non è sicuro o è malformato. Ricostruisci questo indice legacy prima della query.",
    "Build input catalog unexpectedly resolved to None.":
        "Il catalogo di input della costruzione è stato risolto inaspettatamente come None.",
    "Could not normalize gaussian_aperture throughput for these settings.":
        "Impossibile normalizzare il throughput gaussian_aperture con queste impostazioni.",
    "radial_weight contamination model requires radial_weight_file.":
        "Il modello di contaminazione radial_weight richiede radial_weight_file.",
    "radial_weight contamination weighting requires a loaded radial weight table.":
        "La pesatura radial_weight richiede una tabella di pesi radiali caricata.",
    "special_ids.npz uses the legacy unsafe object format. Rebuild the index.":
        "special_ids.npz usa il formato legacy non sicuro a oggetti. Ricostruisci l'indice.",
    "Provide at least one --config or --result-json.": "Specifica almeno un --config o --result-json.",
    "Matplotlib plotting requires the optional matplotlib package.":
        "I grafici Matplotlib richiedono il pacchetto opzionale matplotlib.",
    "Parquet export requires pandas and pyarrow.": "L'esportazione Parquet richiede pandas e pyarrow.",
    "Require 0 <= accept_max_percent <= review_max_percent.":
    "È richiesto 0 <= accept_max_percent <= review_max_percent.",
    "PHOTO-CAT report": "Report PHOTO-CAT",
    "Source result": "Risultato sorgente",
    "PHOTO-CAT target screening": "Screening dei target PHOTO-CAT",
    "Rank": "Posizione",
    "Source ID": "ID sorgente",
    "Decision": "Decisione",
    "Risk (%)": "Rischio (%)",
    "Reasons": "Motivi",
    "accept": "accetta",
    "review": "revisiona",
    "reject": "respingi",
    "unresolved": "non risolto",
    "Build step finished.": "Fase di costruzione terminata.",
    "Summary saved to: {path}": "Riepilogo salvato in: {path}",
    "Plot saved to: {path}": "Grafico salvato in: {path}",
    "Publication plots saved under: {path}": "Grafici da pubblicazione salvati in: {path}",
    "Publication plot manifest saved to: {path}": "Manifest dei grafici da pubblicazione salvato in: {path}",
    "Report saved to: {path}": "Report salvato in: {path}",
    "Export saved to: {path}": "Esportazione salvata in: {path}",
    "Screening decisions saved to: {path}": "Decisioni di screening salvate in: {path}",
    "Validation statistics saved to: {path}": "Statistiche di validazione salvate in: {path}",
    "Matched validation rows saved to: {path}": "Righe di validazione abbinate salvate in: {path}",
    "Provenance saved to: {path}": "Provenienza salvata in: {path}",
    "Benchmark saved to: {path}": "Benchmark salvato in: {path}",
    "Benchmark table saved to: {path}": "Tabella benchmark salvata in: {path}",
    "Reproduction manifest saved to: {path}": "Manifest di riproduzione salvato in: {path}",
    "Merged catalogue saved to: {path}": "Catalogo unito salvato in: {path}",
    "Merge provenance saved to: {path}": "Provenienza dell'unione salvata in: {path}",
    "Loading input catalog...": "Caricamento del catalogo di input...",
    "Loading index data...": "Caricamento dei dati dell'indice...",
    "Index data loaded.": "Dati dell'indice caricati.",
    "Building cKDTree in memory...": "Costruzione della cKDTree in memoria...",
    "Building neighbor index (resumable mode)...": "Costruzione dell'indice dei vicini (modalità ripristinabile)...",
    "No checkpoint found. Starting from the beginning.": "Nessun checkpoint trovato. Avvio dall'inizio.",
    "Catalog column mapping:": "Mappatura delle colonne del catalogo:",
    "Converting RA/Dec to 3D unit vectors...": "Conversione di AR/Dec in vettori unitari 3D...",
    "Computing chordal radius from angular separation...": "Calcolo del raggio cordale dalla separazione angolare...",
    "A complete index already matches the current catalog and settings.":
        "Esiste già un indice completo compatibile con il catalogo e le impostazioni correnti.",
    "Build inputs changed; replacing the existing index.":
        "Gli input di costruzione sono cambiati; sostituzione dell'indice esistente.",

    # CLI command descriptions.
    "open the graphical configurator": "apre il configuratore grafico",
    "run the configured build/query pipeline": "esegue la pipeline di costruzione/query configurata",
    "build the neighbour index from the configured catalogue": "costruisce l'indice dei vicini dal catalogo configurato",
    "query contamination from an existing neighbour index": "calcola la contaminazione da un indice dei vicini esistente",
    "summarize a PHOTO-CAT query result JSON": "riassume un JSON di risultati PHOTO-CAT",
    "write an SVG plot from a PHOTO-CAT query result JSON": "genera un grafico da un JSON di risultati PHOTO-CAT",
    "generate contamination distributions and an accessible sky map": "genera distribuzioni di contaminazione e una mappa del cielo accessibile",
    "export a PHOTO-CAT query result JSON to CSV or Parquet": "esporta un JSON di risultati PHOTO-CAT in CSV o Parquet",
    "rank targets and assign contamination-screening decisions": "classifica i target e assegna decisioni di screening",
    "compare PHOTO-CAT predictions with a reference contamination table": "confronta le previsioni PHOTO-CAT con una tabella di riferimento",
    "write an HTML or Markdown report from a PHOTO-CAT query result JSON": "genera un report HTML o Markdown da un JSON PHOTO-CAT",
    "run selected stages and write benchmark metadata": "esegue le fasi selezionate e salva i metadata del benchmark",
    "render benchmark JSON captures as a Markdown or CSV table": "converte benchmark JSON in una tabella Markdown o CSV",
    "generate reproducible summaries, plots, reports, and a manifest": "genera riassunti, grafici, report e manifest riproducibili",
    "merge a Gaia-like catalogue with a supplemental bright-star table": "unisce un catalogo in stile Gaia con una tabella di stelle brillanti",
    "write catalogue provenance metadata": "salva i metadata di provenienza del catalogo",
    "run diagnostic checks": "esegue i controlli diagnostici",

    # CLI option guidance. Command names, format choices, and schema fields stay stable.
    "show the installed PHOTO-CAT version and exit": "mostra la versione installata di PHOTO-CAT ed esce",
    "configuration file to edit/use": "file di configurazione da modificare o usare",
    "configuration file to use": "file di configurazione da usare",
    "catalogue CSV path": "percorso del CSV del catalogo",
    "output/index directory for the build step": "cartella di output/indice per la fase di costruzione",
    "legacy comma-separated column list: source_id,ra,dec,mag":
        "elenco colonne legacy separato da virgole: source_id,ra,dec,mag",
    "catalogue source_id column name": "nome della colonna source_id del catalogo",
    "catalogue right-ascension column name": "nome della colonna di ascensione retta del catalogo",
    "catalogue declination column name": "nome della colonna di declinazione del catalogo",
    "catalogue magnitude column name": "nome della colonna di magnitudine del catalogo",
    "optional comma-separated band=column magnitude map, e.g. gaia_bp=phot_bp_mean_mag,gaia_rp=phot_rp_mean_mag":
        "mappa opzionale banda=colonna separata da virgole, per esempio gaia_bp=phot_bp_mean_mag,gaia_rp=phot_rp_mean_mag",
    "enable or disable Dask catalogue loading": "abilita o disabilita il caricamento del catalogo con Dask",
    "write neighbour separations during index building": "salva le separazioni dei vicini durante la costruzione dell'indice",
    "maximum neighbour search radius in arcseconds": "raggio massimo di ricerca dei vicini in arcosecondi",
    "catalogue processing chunk size": "numero di righe del catalogo elaborate per blocco",
    "row interval used when flushing neighbour buffers": "intervallo di righe per il salvataggio dei buffer dei vicini",
    "existing output/index directory used by the query step": "cartella output/indice esistente usata dalla query",
    "comma-separated manual target source IDs": "ID sorgente dei target manuali separati da virgole",
    "circular extraction/screening aperture radius in arcseconds":
        "raggio in arcosecondi dell'apertura circolare di estrazione o screening",
    "outer radius searched for weighted leakage; must cover the aperture":
        "raggio esterno per la dispersione pesata della luce; deve includere l'apertura",
    "maximum contaminant-target magnitude difference": "massima differenza di magnitudine contaminante-target",
    "comma-separated magnitude bands to compute; use all to query every band stored in the index":
        "bande da calcolare separate da virgole; usa all per tutte le bande presenti nell'indice",
    "aperture weighting model for flux metrics": "modello di pesatura dell'apertura per le metriche di flusso",
    "Gaussian PSF FWHM when using gaussian_psf mode": "FWHM della PSF gaussiana per la modalità gaussian_psf",
    "CSV file with sep_arcsec,weight columns for radial_weight mode":
        "file CSV con colonne sep_arcsec,weight per la modalità radial_weight",
    "enable or disable the build stage": "abilita o disabilita la fase di costruzione",
    "enable or disable the query stage": "abilita o disabilita la fase di query",
    "replace an already-running launcher pipeline session": "sostituisce una sessione pipeline già in esecuzione",
    "PHOTO-CAT query result JSON": "JSON dei risultati di una query PHOTO-CAT",
    "summary output format (default: text)": "formato del riepilogo (predefinito: text)",
    "optional output path": "percorso di output opzionale",
    "plot type (default: contaminant-counts)": "tipo di grafico (predefinito: contaminant-counts)",
    "plot backend (default: svg)": "backend grafico (predefinito: svg)",
    "SVG output path": "percorso del file SVG di output",
    "aperture represented by the result": "apertura rappresentata dal risultato",
    "directory for plots and manifest": "cartella per grafici e manifest",
    "raster resolution (default: 300)": "risoluzione raster (predefinita: 300)",
    "export output path": "percorso dell'esportazione",
    "export format (default: csv)": "formato di esportazione (predefinito: csv)",
    "screening output path": "percorso del risultato di screening",
    "result metric used as the risk score": "metrica del risultato usata come punteggio di rischio",
    "reference contamination CSV": "CSV di contaminazione di riferimento",
    "validation statistics JSON": "JSON delle statistiche di validazione",
    "optional matched residual CSV": "CSV opzionale dei residui abbinati",
    "report format (default: html)": "formato del report (predefinito: html)",
    "report output path": "percorso del report",
    "benchmark JSON output path": "percorso del benchmark JSON",
    "include or skip the build stage": "include o salta la fase di costruzione",
    "include or skip the query stage": "include o salta la fase di query",
    "benchmark JSON file(s)": "file JSON di benchmark",
    "table output path": "percorso della tabella di output",
    "run configuration file; may be provided multiple times":
        "file di configurazione da eseguire; può essere specificato più volte",
    "existing result JSON to include; may be provided multiple times":
        "JSON di risultati esistente da includere; può essere specificato più volte",
    "directory for manifest and generated products": "cartella per manifest e prodotti generati",
    "run each provided config before collecting the latest result JSON":
        "esegue ogni configurazione prima di raccogliere il JSON di risultati più recente",
    "plot backend for generated products (default: svg)":
        "backend grafico per i prodotti generati (predefinito: svg)",
    "base Gaia-like catalogue CSV": "CSV del catalogo di base in stile Gaia",
    "supplemental bright-star catalogue CSV": "CSV supplementare delle stelle brillanti",
    "merged catalogue CSV path": "percorso del catalogo CSV unito",
    "source ID column shared by both CSVs": "colonna ID sorgente condivisa dai due CSV",
    "which table wins duplicate source IDs": "tabella da preferire per gli ID sorgente duplicati",
    "optional JSON metadata path for the merge": "percorso opzionale dei metadata JSON dell'unione",
    "provenance JSON output path": "percorso del JSON di provenienza",
    "optional ADQL/query file used to create the catalogue": "file ADQL/query opzionale usato per creare il catalogo",
    "source ID column name": "nome della colonna ID sorgente",
    "right-ascension column name": "nome della colonna di ascensione retta",
    "declination column name": "nome della colonna di declinazione",
    "magnitude column name": "nome della colonna di magnitudine",
    "optional configuration file for environment context": "file di configurazione opzionale per il contesto dell'ambiente",
    "diagnostic output format (default: text)": "formato della diagnostica (predefinito: text)",
}


# Ordered dynamic fragments translate values-bearing errors/logs at display time.
ITALIAN_FRAGMENTS: tuple[tuple[str, str], ...] = (
    ("Could not read", "Impossibile leggere"),
    ("Could not load", "Impossibile caricare"),
    ("Could not save", "Impossibile salvare"),
    ("Could not start", "Impossibile avviare"),
    ("was not found", "non è stato trovato"),
    ("is missing", "non contiene"),
    ("must be", "deve essere"),
    ("must have", "deve avere"),
    ("must use", "deve usare"),
    ("must match", "deve corrispondere a"),
    ("must exist", "deve esistere"),
    ("must be one of", "deve essere uno tra"),
    ("positive finite number", "numero positivo e finito"),
    ("positive integer", "numero intero positivo"),
    ("cannot be empty", "non può essere vuoto"),
    ("must contain", "deve contenere"),
    ("must not exceed", "non deve superare"),
    ("is required", "è obbligatorio"),
    ("invalid choice", "scelta non valida"),
    ("Invalid", "Non valido"),
    ("invalid", "non valido"),
    ("unrecognized arguments", "argomenti non riconosciuti"),
    ("the following arguments are required", "sono richiesti i seguenti argomenti"),
    ("expected one argument", "richiede un argomento"),
    ("not allowed with argument", "non è consentito insieme all'argomento"),
    ("choose from", "scegli tra"),
    ("argument ", "argomento "),
    ("Missing", "Mancante"),
    ("missing", "mancante"),
    ("Unsupported", "Non supportato"),
    ("not present", "non presente"),
    ("not installed", "non installato"),
    ("not available", "non disponibile"),
    ("only needed when no suitable system Python exists", "necessario solo se non è disponibile un Python di sistema adatto"),
    ("not installed in this environment", "non installato in questo ambiente"),
    ("not checked in package-install mode", "non controllato nella modalità di installazione del pacchetto"),
    ("not checked; pass --config when validating a run configuration", "non controllato; usa --config per validare una configurazione di esecuzione"),
    ("run a launcher to create the local environment", "esegui un launcher per creare l'ambiente locale"),
    ("run a launcher to rebuild it", "esegui un launcher per ricostruirlo"),
    ("exists but is not a folder", "esiste ma non è una cartella"),
    ("stale project marker points to", "il riferimento obsoleto del progetto punta a"),
    ("missing Python executable at", "eseguibile Python mancante in"),
    ("Python executable at", "eseguibile Python in"),
    ("installed", "installato"),
    ("expected", "previsto"),
    ("No ", "Nessun "),
    ("loading catalog", "caricamento catalogo"),
    ("loading index arrays", "caricamento array dell'indice"),
    ("opening neighbour memory map", "apertura della mappa in memoria dei vicini"),
    ("building KDTree", "costruzione KDTree"),
    ("saving index outputs", "salvataggio output dell'indice"),
    ("saving JSON results", "salvataggio risultati JSON"),
    ("processing targets", "elaborazione target"),
    ("downloading/installing", "download/installazione di"),
    ("downloading/upgrading", "download/aggiornamento di"),
    ("building/installing", "costruzione/installazione di"),
    ("is unavailable", "non è disponibile"),
    ("outside-aperture weighted flux", "flusso pesato esterno all'apertura"),
    ("Failed", "Operazione non riuscita"),
    ("passed", "superati"),
    ("warnings", "avvisi"),
    ("failed", "non riusciti"),
    ("Results saved to:", "Risultati salvati in:"),
    ("Run metadata saved to:", "Metadata dell'esecuzione salvati in:"),
    ("Index saved to:", "Indice salvato in:"),
    ("Summary saved to:", "Riepilogo salvato in:"),
    ("Plot saved to:", "Grafico salvato in:"),
    ("Report saved to:", "Report salvato in:"),
    ("Export saved to:", "Esportazione salvata in:"),
    ("Loading catalog:", "Caricamento catalogo:"),
    ("Loaded", "Caricate"),
    ("rows", "righe"),
    ("sources", "sorgenti"),
    ("targets", "target"),
    ("neighbors", "vicini"),
    ("neighbours", "vicini"),
    ("Step", "Fase"),
    ("of", "di"),
    ("Reason:", "Motivo:"),
    ("Details:", "Dettagli:"),
    ("Warning", "Avviso"),
    ("Error", "Errore"),
)


TOOLTIPS_EN: dict[str, str] = {
    "Language": "Changes GUI labels, help, dialogs, command output, warnings, and expected errors between English and Italian.",
    "Catalog CSV": "The main table of stars. It must contain one row per source, sky coordinates, a unique source ID, and at least one magnitude.",
    "Catalog Source ID column": "The column containing the unique identifier of each catalogue source, such as Gaia source_id.",
    "Catalog RA column": "Right ascension: the east-west sky coordinate, expressed in decimal degrees from 0 to 360.",
    "Catalog Dec column": "Declination: the north-south sky coordinate, expressed in decimal degrees from -90 to +90.",
    "Catalog magnitude column": "The brightness measurement used for the default flux ratio. Smaller magnitudes mean brighter sources.",
    "Magnitude bands (optional extra bands)": "Map additional photometric bands to CSV columns so contamination can be compared at different wavelengths.",
    "Targets CSV": "The stars you want to evaluate. Their source IDs must also exist in the catalogue used to build the index.",
    "Output/index folder": "Where PHOTO-CAT stores the reusable neighbour index and generated query results.",
    "Query index folder": "The previously built index that the contamination query will read.",
    "Manual targets": "Use this list when you want to analyse a few source IDs without creating a separate target CSV.",
    "Max build radius, arcsec": "Largest neighbour distance stored in the index. It must cover every aperture or influence radius you plan to query.",
    "Query aperture radius, arcsec": "Radius of the circular measurement region around each target. One arcsecond is 1/3600 of a degree.",
    "Outer influence radius, arcsec": "Optional larger radius used by weighted models to include light leaking into the aperture from nearby stars outside it.",
    "Delta magnitude": "Maximum neighbour-minus-target magnitude difference. A value of 5 includes neighbours up to 100 times fainter than the target.",
    "Contamination bands (comma-separated, or all)": "Photometric bands used to calculate flux ratios. Use all to process every band stored in the index.",
    "Bandpass profile YAML (optional)": "A calibrated colour transformation that estimates magnitudes in an instrument or mission-specific band.",
    "Contamination weighting model": "Controls how strongly a neighbour contributes according to its distance from the target and the aperture response.",
    "Gaussian FWHM, arcsec": "Full width at half maximum of the Gaussian response. It describes the apparent width of a point source.",
    "Radial weight CSV": "A two-column sep_arcsec/weight calibration describing how source contribution changes with angular distance.",
    "Use Dask for very large CSV files": "Processes large catalogues in partitions to reduce peak memory use. It may add overhead for small files.",
    "Store neighbor separations on disk": "Precomputes angular separations during index construction, making later queries faster at the cost of disk space.",
    "Run build step": "Creates or refreshes the neighbour index from the catalogue.",
    "Run query step": "Evaluates the selected targets using an existing compatible index.",
    "Include missing target rows in results": "Keeps requested IDs that cannot be evaluated, with an explicit status instead of silently omitting them.",
    "Chunk size": "Number of catalogue rows processed together. Larger values can be faster but require more memory.",
    "Buffer flush / checkpoint every N chunks": "How often intermediate neighbour data is safely saved so a long build can resume after interruption.",
    "Result JSON": "The machine-readable target results produced by a PHOTO-CAT query.",
    "Metric": "The numeric contamination field used for ranking or comparison. The total weighted flux percentage is usually the safest screening choice.",
    "Accept max percent": "Targets at or below this contamination percentage are classified as acceptable.",
    "Review max percent": "Targets above the accept limit but at or below this value require manual review; larger values are rejected.",
    "Aperture, arcsec": "The aperture radius represented by the selected result. This label is recorded in publication metadata.",
    "DPI": "Raster resolution in dots per inch. Use 300 or more for most journal submissions.",
    "Reference CSV": "An external table of measured or independently estimated contamination used to validate PHOTO-CAT predictions.",
    "Source ID column": "The column used to match the same star across input tables.",
    "Reference column": "The reference-table column containing contamination percentages.",
    "Threshold percent (optional)": "Optional boundary used to compare contaminated/not-contaminated classifications.",
    "Benchmark": "Measures runtime and memory on the current machine so performance claims can be reproduced.",
    "Doctor": "Checks Python, dependencies, configuration, paths, and index health without running the full analysis.",
}


TOOLTIPS_IT: dict[str, str] = {
    "Language": "Cambia fra inglese e italiano le etichette GUI, l'aiuto, le finestre, l'output dei comandi, gli avvisi e gli errori previsti.",
    "Catalog CSV": "La tabella principale delle stelle. Deve contenere una riga per sorgente, coordinate celesti, un ID univoco e almeno una magnitudine.",
    "Catalog Source ID column": "La colonna con l'identificatore univoco di ogni sorgente, per esempio Gaia source_id.",
    "Catalog RA column": "Ascensione retta: coordinata est-ovest nel cielo, espressa in gradi decimali da 0 a 360.",
    "Catalog Dec column": "Declinazione: coordinata nord-sud nel cielo, espressa in gradi decimali da -90 a +90.",
    "Catalog magnitude column": "Misura di luminosità usata per il rapporto di flusso predefinito. Magnitudini più piccole indicano sorgenti più luminose.",
    "Magnitude bands (optional extra bands)": "Associa bande fotometriche aggiuntive alle colonne CSV per confrontare la contaminazione a diverse lunghezze d'onda.",
    "Targets CSV": "Le stelle da valutare. I loro ID devono esistere anche nel catalogo usato per costruire l'indice.",
    "Output/index folder": "Cartella in cui PHOTO-CAT salva l'indice riutilizzabile dei vicini e i risultati delle query.",
    "Query index folder": "Indice costruito in precedenza che verrà letto dalla query di contaminazione.",
    "Manual targets": "Usa questo elenco per analizzare pochi ID senza creare un CSV dei target separato.",
    "Max build radius, arcsec": "Massima distanza dei vicini salvata nell'indice. Deve coprire ogni apertura o raggio di influenza che userai.",
    "Query aperture radius, arcsec": "Raggio della regione circolare attorno al target. Un arcosecondo equivale a 1/3600 di grado.",
    "Outer influence radius, arcsec": "Raggio più grande usato dai modelli pesati per includere luce proveniente da stelle esterne all'apertura.",
    "Delta magnitude": "Massima differenza magnitudine_vicino - magnitudine_target. Il valore 5 include vicini fino a 100 volte più deboli.",
    "Contamination bands (comma-separated, or all)": "Bande fotometriche usate nei rapporti di flusso. Usa all per elaborare tutte le bande nell'indice.",
    "Bandpass profile YAML (optional)": "Trasformazione di colore calibrata per stimare magnitudini in una banda specifica dello strumento o missione.",
    "Contamination weighting model": "Stabilisce quanto contribuisce un vicino in funzione della distanza dal target e della risposta dell'apertura.",
    "Gaussian FWHM, arcsec": "Larghezza a metà altezza della risposta gaussiana; descrive la larghezza apparente di una sorgente puntiforme.",
    "Radial weight CSV": "Calibrazione sep_arcsec/weight che descrive come varia il contributo con la distanza angolare.",
    "Use Dask for very large CSV files": "Elabora cataloghi grandi in partizioni per ridurre la memoria massima; può rallentare file piccoli.",
    "Store neighbor separations on disk": "Precalcola le separazioni durante la costruzione, velocizzando le query al costo di spazio su disco.",
    "Run build step": "Crea o aggiorna l'indice dei vicini dal catalogo. È necessario quando cambiano catalogo, colonne, raggio massimo o bande salvate.",
    "Run query step": "Valuta i target selezionati usando un indice compatibile già esistente.",
    "Include missing target rows in results": "Conserva gli ID non valutabili con uno stato esplicito invece di ometterli.",
    "Chunk size": "Numero di righe elaborate insieme. Valori maggiori possono essere più veloci ma richiedono più memoria.",
    "Buffer flush / checkpoint every N chunks": "Frequenza di salvataggio dei dati intermedi, utile per riprendere costruzioni lunghe dopo un'interruzione.",
    "Result JSON": "Risultati dei target prodotti da una query PHOTO-CAT in formato leggibile dalle macchine.",
    "Metric": "Campo numerico usato per classifica o confronto. La percentuale di flusso totale pesato è spesso la scelta più prudente.",
    "Accept max percent": "I target con contaminazione uguale o inferiore vengono classificati come accettabili.",
    "Review max percent": "I target fra limite di accettazione e questo valore richiedono revisione; quelli superiori vengono respinti.",
    "Aperture, arcsec": "Raggio dell'apertura rappresentata dal risultato. Il valore viene registrato nei metadata da pubblicazione.",
    "DPI": "Risoluzione raster in punti per pollice. Per molte riviste sono consigliati almeno 300 DPI.",
    "Reference CSV": "Tabella esterna con contaminazione misurata o stimata indipendentemente, usata per validare PHOTO-CAT.",
    "Source ID column": "Colonna usata per riconoscere la stessa stella nelle diverse tabelle.",
    "Reference column": "Colonna della tabella di riferimento contenente le percentuali di contaminazione.",
    "Threshold percent (optional)": "Confine opzionale per confrontare le classificazioni contaminato/non contaminato.",
    "Benchmark": "Misura tempo e memoria sulla macchina corrente per rendere riproducibili le prestazioni.",
    "Doctor": "Controlla Python, dipendenze, configurazione, percorsi e indice senza eseguire l'intera analisi.",
}


# Guidance for secondary tools and output fields. These remain explicit instead
# of relying on the generic fallback so a first-time user can choose safely.
TOOLTIPS_EN.update({
    "Format": "Selects how the product is encoded, such as readable text, machine-readable JSON, CSV, HTML, Markdown, PNG, PDF, or SVG.",
    "Kind": "Selects which scientific relationship the plot displays; the input data are not changed.",
    "Backend": "Selects the plotting engine. SVG is lightweight; matplotlib supports raster and publication workflows.",
    "Config file": "The YAML file containing catalogue paths, scientific settings, and execution choices for one run.",
    "Config file (optional)": "Optional YAML configuration used to give this tool the same project and language context as a run.",
    "Config files": "One or more YAML run configurations to include in a reproducible product bundle.",
    "Result JSON files": "One or more completed PHOTO-CAT result files to include without rerunning their queries.",
    "Output directory": "Folder that will receive all generated files; existing unrelated files are left untouched.",
    "Output data file (path)": "Destination filename for an exported CSV or Parquet table.",
    "Output image file (path; auto-named next to the result if blank)": "Destination for the plot. Leave blank to create a descriptive filename beside the result JSON.",
    "Output report file (path; auto-named next to the result if blank)": "Destination for the HTML or Markdown report. Leave blank for an automatic filename.",
    "Output summary file (optional; prints to console if blank)": "Optional destination for the summary; leaving it blank shows the summary in the console only.",
    "Output screening file (path)": "Destination for the ranked accept/review/reject decisions.",
    "Output table file (path)": "Destination for the combined benchmark table. Choose .md for readable Markdown or .csv for further analysis.",
    "Output (JSON)": "Destination for a machine-readable JSON data or metadata product. Use a new filename to avoid overwriting prior evidence.",
    "Output (stats JSON)": "Destination for validation statistics such as bias, MAE, and RMSE.",
    "Output (merged CSV)": "Destination for the catalogue produced by combining the base and bright-star tables.",
    "Matched residuals CSV file (optional)": "Optional row-by-row validation table for inspecting individual prediction errors.",
    "Provenance output (optional)": "Optional JSON record of input files, checksums, settings, and merge choices.",
    "ADQL file (optional)": "Optional Gaia ADQL query text recorded with the catalogue provenance so its selection can be reproduced.",
    "Base catalog CSV": "Main Gaia-like catalogue that will receive any missing supplemental bright stars.",
    "Bright-star catalog CSV": "Supplemental bright-source table used to reduce incompleteness at the luminous end of the main catalogue.",
    "Prefer on duplicates": "Chooses which table supplies a row when the same source ID occurs in both catalogues.",
    "Benchmark JSON files": "Performance captures to combine; compare runs only when catalogue size, radius, hardware, and settings are comparable.",
    "Run build stage": "Include index construction in the timed or reproducible workflow.",
    "Run query stage": "Include target contamination evaluation in the timed or reproducible workflow.",
    "Run each config before collecting results": "Reruns every selected configuration; disable it to package results that already exist.",
    "RA column": "Column containing right ascension in decimal degrees, the east-west sky coordinate from 0 to 360.",
    "Dec column": "Column containing declination in decimal degrees, the north-south sky coordinate from -90 to +90.",
    "Magnitude column": "Column containing brightness measurements; smaller astronomical magnitudes correspond to brighter stars.",
    "Summarize results": "Calculates target counts and mean, median, and maximum contamination metrics from a result JSON.",
    "Screen / rank targets": "Orders targets by risk and applies explicit thresholds for accept, review, reject, or unresolved decisions.",
    "Plot (SVG / matplotlib)": "Creates a scientific diagnostic plot from result rows without changing the underlying measurements.",
    "Publication plots": "Creates coordinated count, separation, and sky-map products plus a checksummed manifest.",
    "Report": "Combines a human-readable summary and plots into HTML or Markdown.",
    "Export": "Converts target-result rows into CSV or Parquet for spreadsheets, notebooks, or other analysis tools.",
    "Validate results": "Compares predicted contamination with an independent reference table matched by source ID.",
    "Catalogue provenance": "Records catalogue checksum, dimensions, columns, value ranges, and optional query provenance.",
    "Merge bright stars": "Adds a supplemental bright-star table to a Gaia-like catalogue while resolving duplicate IDs explicitly.",
    "Benchmark pipeline": "Measures selected pipeline stages and records runtime, memory, catalogue size, radius, and hardware context.",
    "Benchmark table": "Combines benchmark captures into a comparison table suitable for review or publication notes.",
    "Reproduce": "Collects configs, results, summaries, reports, plots, checksums, and versions into a traceable bundle.",
    "Doctor diagnostics": "Checks whether Python, dependencies, configuration, folders, and the local environment are ready.",
    "Run diagnostics": "Runs read-only health checks; it does not build an index or modify scientific results.",
})

TOOLTIPS_IT.update({
    "Format": "Seleziona la codifica del prodotto: testo leggibile, JSON, CSV, HTML, Markdown, PNG, PDF oppure SVG.",
    "Kind": "Seleziona la relazione scientifica mostrata dal grafico; i dati di input non vengono modificati.",
    "Backend": "Seleziona il motore grafico. SVG è leggero; matplotlib supporta raster e flussi da pubblicazione.",
    "Config file": "File YAML con percorsi del catalogo, impostazioni scientifiche e scelte di esecuzione.",
    "Config file (optional)": "Configurazione YAML opzionale che fornisce allo strumento lo stesso contesto di progetto e lingua.",
    "Config files": "Una o più configurazioni YAML da includere in un pacchetto riproducibile.",
    "Result JSON files": "Uno o più risultati PHOTO-CAT già completati da includere senza rieseguire le query.",
    "Output directory": "Cartella che riceverà i file generati; i file estranei già presenti non vengono toccati.",
    "Output data file (path)": "Nome del file di destinazione per una tabella CSV o Parquet esportata.",
    "Output image file (path; auto-named next to the result if blank)": "Destinazione del grafico. Lascia vuoto per creare un nome descrittivo accanto al JSON.",
    "Output report file (path; auto-named next to the result if blank)": "Destinazione del report HTML o Markdown. Lascia vuoto per un nome automatico.",
    "Output summary file (optional; prints to console if blank)": "Destinazione opzionale del riepilogo; se vuota, il riepilogo appare solo nella console.",
    "Output screening file (path)": "Destinazione delle decisioni classificate accept/review/reject.",
    "Output table file (path)": "Destinazione della tabella combinata dei benchmark. Scegli .md per Markdown leggibile o .csv per altre analisi.",
    "Output (JSON)": "Destinazione di un prodotto dati o metadata in formato JSON.",
    "Output (stats JSON)": "Destinazione delle statistiche di validazione, come bias, MAE e RMSE.",
    "Output (merged CSV)": "Destinazione del catalogo ottenuto unendo tabella di base e stelle brillanti.",
    "Matched residuals CSV file (optional)": "Tabella opzionale riga per riga per esaminare i singoli errori di previsione.",
    "Provenance output (optional)": "Registro JSON opzionale di input, checksum, impostazioni e scelte di unione.",
    "ADQL file (optional)": "Query Gaia ADQL opzionale registrata con la provenienza per riprodurre la selezione.",
    "Base catalog CSV": "Catalogo principale in stile Gaia al quale aggiungere eventuali stelle brillanti mancanti.",
    "Bright-star catalog CSV": "Tabella supplementare di sorgenti brillanti che riduce l'incompletezza del catalogo principale.",
    "Prefer on duplicates": "Sceglie quale tabella fornisce la riga quando lo stesso ID appare in entrambi i cataloghi.",
    "Benchmark JSON files": "Misure da combinare; confronta solo esecuzioni con dimensione, raggio, hardware e impostazioni comparabili.",
    "Run build stage": "Include la costruzione dell'indice nel flusso cronometrato o riproducibile.",
    "Run query stage": "Include la valutazione della contaminazione dei target nel flusso cronometrato o riproducibile.",
    "Run each config before collecting results": "Riesegue ogni configurazione; disabilita per raccogliere risultati già esistenti.",
    "RA column": "Colonna dell'ascensione retta in gradi decimali, coordinata est-ovest da 0 a 360.",
    "Dec column": "Colonna della declinazione in gradi decimali, coordinata nord-sud da -90 a +90.",
    "Magnitude column": "Colonna della luminosità; magnitudini astronomiche minori indicano stelle più brillanti.",
    "Summarize results": "Calcola conteggi e media, mediana e massimo delle metriche di contaminazione.",
    "Screen / rank targets": "Ordina i target per rischio e applica soglie esplicite per accept, review, reject o unresolved.",
    "Plot (SVG / matplotlib)": "Crea un grafico diagnostico scientifico senza cambiare le misure sottostanti.",
    "Publication plots": "Crea prodotti coordinati di conteggio, separazione e mappa celeste con manifest e checksum.",
    "Report": "Combina riepilogo leggibile e grafici in HTML o Markdown.",
    "Export": "Converte i risultati in CSV o Parquet per fogli di calcolo, notebook o altre analisi.",
    "Validate results": "Confronta la contaminazione prevista con una tabella indipendente abbinata per ID sorgente.",
    "Catalogue provenance": "Registra checksum, dimensioni, colonne, intervalli e query opzionale del catalogo.",
    "Merge bright stars": "Aggiunge stelle brillanti a un catalogo in stile Gaia risolvendo esplicitamente gli ID duplicati.",
    "Benchmark pipeline": "Misura fasi della pipeline e registra tempo, memoria, dimensione, raggio e contesto hardware.",
    "Benchmark table": "Combina misure di benchmark in una tabella per revisione o note di pubblicazione.",
    "Reproduce": "Raccoglie configurazioni, risultati, riepiloghi, report, grafici, checksum e versioni in un pacchetto tracciabile.",
    "Doctor diagnostics": "Controlla Python, dipendenze, configurazione, cartelle e ambiente locale.",
    "Run diagnostics": "Esegue controlli di sola lettura; non costruisce indici e non modifica risultati scientifici.",
})

TOOLTIPS_EN.update({
    "PHOTO-CAT": "PHOTO-CAT is a catalogue-level contamination risk and target-screening application. Start with Files & columns, then Search settings, and finally Run options.",
    "Photometric Contamination Analyzer Tool - configure the pipeline and run every command.": "This window configures the complete workflow: prepare an index, query targets, inspect results, validate predictions, and create reproducible products.",
    "Switch to light mode": "Changes only the GUI appearance to a light colour theme. Scientific values, configuration, files, and plot palettes are not modified.",
    "Switch to dark mode": "Changes only the GUI appearance to a dark colour theme. Scientific values, configuration, files, and plot palettes are not modified.",
    "Configure pipeline": "These sections define the input catalogue, coordinate and magnitude columns, search geometry, contamination model, and stages to execute.",
    "Files & columns": "Open the input-data section. Select catalogue and targets files, then verify that every configured column exactly matches its CSV header.",
    "Run options": "Open execution controls that decide whether to build an index, query targets, retain missing IDs, and replace an existing pipeline window.",
    "Results": "Commands in this group inspect, rank, plot, report, export, or validate an existing query-result JSON.",
    "Catalogue": "Commands in this group document catalogue provenance or merge a supplemental bright-star table before index construction.",
    "Diagnostics": "Environment health checks that do not alter catalogue indexes or scientific results.",
    "Summarize": "Open the summary tool to calculate aggregate target counts and contamination statistics from a result JSON.",
    "Screen / rank": "Open target screening to rank risk scores and assign accept, review, reject, or unresolved decisions from explicit thresholds.",
    "Plot (SVG)": "Open diagnostic plotting. Select a result JSON and relationship; SVG needs no plotting backend, while matplotlib supports additional formats.",
    "Provenance": "Open catalogue provenance capture to record checksums, row counts, columns, ranges, and the optional source ADQL query.",
    "Files and columns": "Define the tables PHOTO-CAT reads and map their CSV headers to source ID, sky-coordinate, and magnitude roles.",
    "Catalog column names": "These four case-sensitive headers identify each source and provide right ascension, declination, and the default photometric magnitude.",
    "Targets column name": "Set the case-sensitive target-table header containing source IDs. It normally remains source_id.",
    "Search settings": "Choose which neighbours can influence a target and how their catalogue flux is weighted inside or around the aperture.",
    "Model mode": "Select top_hat for simple inclusion, Gaussian modes for a circular PSF approximation, or radial_weight for a calibrated response table.",
    "Advanced performance settings": "Chunk and checkpoint controls affect speed, RAM, disk writes, and resumability, but do not change the intended scientific selection.",
    "Enable advanced settings": "Unlocks chunk size and checkpoint frequency. Leave disabled unless catalogue scale or available memory requires tuning.",
    "Options": "Select the pipeline stages and compatibility behavior for missing targets, stored separations, large CSV loading, and repeated launches.",
    "Use manual list": "Uses source IDs typed in Manual targets instead of requiring a separate targets CSV. The IDs must exist in the built catalogue index.",
    "Replace running pipeline when Save + run is clicked": "When enabled, closes the previous pipeline process started by this GUI before launching another, preventing accidental duplicate heavy runs.",
    "Tool output": "Displays stdout and stderr from result, catalogue, benchmark, and diagnostic tools. It is a viewer; clearing it does not delete output files.",
    "Clear": "Clears the visible tool-output console only. Generated reports, plots, JSON files, indexes, and logs remain on disk.",
    "Help": "Opens a concise workflow guide with recommended first steps, input expectations, and explanations of the contamination models.",
    "Load example config": "Replaces the current form values with the bundled safe example settings. Review paths before saving or running.",
    "Save config.yaml": "Validates the form and writes the current language, paths, scientific settings, and run choices to the project config.yaml without starting the pipeline.",
    "Save + run pipeline": "Validates and saves config.yaml, then launches the selected build/query stages in a separate console. Large catalogues may take substantial time and disk space.",
    "Browse...": "Opens a file or folder chooser for this field. The selected path remains editable before saving.",
    "Add file...": "Adds another file path to this multi-file input without removing paths already listed.",
    "Quick help": "A short recommended workflow for first-time users. Use the detailed field tooltips when choosing scientific values.",
    "Default Gaia-like names are pre-filled. Change them only if your CSV headers are different. The names must match the catalog CSV exactly, including uppercase/lowercase.": "Keep the Gaia-like defaults when those headers exist. A mismatch such as RA instead of ra prevents the catalogue from loading, so compare them with the first CSV row.",
    "Default target column is source_id. Change it only if your targets CSV uses another header. This is case-sensitive. Manual targets ignore this field.": "This maps the target-table identifier to the catalogue source ID. It does not select the catalogue source-ID column, which is configured separately above.",
    "One band=catalog_column per line, for example gaia_bp=phot_bp_mean_mag. gaia_g is always mapped to the catalog magnitude column above. Extra bands can then be requested in Search settings > Contamination bands.": "Store extra catalogue magnitudes only when the named columns exist and contain compatible numeric values. Every requested contamination band must be built into the index first.",
    "Optional. Leave Targets CSV empty/null to use this source_id list instead. Use one source_id per line, or separate them with commas.": "Best for small target sets. Large selections are easier to audit and reproduce with a targets CSV.",
    "The aperture radius defines the extraction/screening circle. The influence radius can be larger when a weighted PSF model should include leakage from nearby sources outside that aperture. Both must be equal to or smaller than the max build radius.": "Choose radii in arcseconds. The build radius is the hard data limit: increasing a query radius later cannot recover neighbours that were never indexed.",
    "top_hat keeps the historical catalogue/aperture flux estimate. gaussian_psf and gaussian_aperture need a Gaussian FWHM. radial_weight needs a CSV of sep_arcsec,weight.": "Use top_hat for preliminary geometric screening. Use a weighted mode only when its FWHM or radial curve reasonably represents the instrument response.",
    "Leave these locked unless you know what you are doing. Wrong values can make the tool slower, use too much RAM, write too often to disk, or make long runs harder to resume safely.": "Chunk size trades memory for throughput; checkpoint frequency trades disk overhead for less lost work after interruption. Test changes on a catalogue subset first.",
    "Enabled: the previous pipeline window opened by this GUI is closed before a new run starts. Disabled: each Save + run opens a separate pipeline window.": "Enable this on normal workstations to avoid two builds competing for RAM and disk. Disable only when intentionally running independent configurations in parallel.",
    "Output from Results / Catalogue / Benchmark / Diagnostics commands appears here.": "Command output includes saved-file paths, summaries, warnings, and expected errors. Pipeline build/query progress appears in its separate console.",
    "Recommended workflow:\n1. Select Catalog CSV in Files & columns.\n2. Check that Targets CSV and output folders were auto-filled correctly.\n3. Leave the Gaia-like column names unchanged unless your CSV uses different headers.\n4. Click Save + run pipeline.\n5. Use the Results and Catalogue panels on the output JSON afterwards.": "Following this order prevents most path and column errors. Start with the bundled example before moving to a large scientific catalogue.",
    "Summarize a PHOTO-CAT query result JSON as text, JSON, or CSV.": "Use text for reading, JSON for automation, or CSV for a one-row statistics table. This command does not recompute target contamination.",
    "Rank targets by a contamination metric and assign accept / review / reject decisions.": "Choose thresholds appropriate to the mission. Accept/review/reject are screening labels, not proof that extracted photometry is unbiased.",
    "Write a plot from a PHOTO-CAT query result JSON.": "Creates one diagnostic relationship from stored result fields. Plot labels remain in English for consistent scientific output.",
    "Generate contaminant-count and separation distributions, and the RA/Dec contamination sky map.": "Creates coordinated publication-oriented products from one result and records settings and checksums in a manifest.",
    "Write an HTML or Markdown report from a PHOTO-CAT query result JSON.": "Builds a portable human-readable summary. HTML embeds diagnostic SVG plots; Markdown is convenient for repositories and review notes.",
    "Export target-result rows to CSV or Parquet.": "CSV is broadly compatible; Parquet preserves tabular types and is usually smaller and faster for large analyses.",
    "Compare PHOTO-CAT predictions with an external reference contamination table.": "Matches rows by source ID and reports residual statistics. Ensure both tables use the same percentage definition and aperture before interpreting agreement.",
    "Capture provenance metadata for a catalogue CSV.": "Records identity and descriptive metadata so catalogue selections can be cited, checked for change, and reproduced later.",
    "Merge a Gaia-like base catalogue with a supplemental bright-star table.": "Use before building the index when the base catalogue may omit saturated or exceptionally bright sources. Review duplicate preference carefully.",
    "Run selected pipeline stages using the current config and write benchmark metadata JSON. Uses the config.yaml saved by this GUI unless you pick another config file.": "Benchmark comparable configurations on an otherwise idle machine and record catalogue size, radius, hardware, runtime, and memory together.",
    "Render one or more benchmark JSON captures as a Markdown or CSV table.": "Use Markdown for a readable paper/review table and CSV for further analysis. Comparing unlike radii or catalogues can be misleading.",
    "Generate reproducible summaries, plots, reports, and a manifest from configs and/or result JSONs.": "Packages inputs and derived products with versions and checksums. Enable rerun only when you intend to execute every supplied configuration again.",
    "Run environment and configuration diagnostic checks.": "Performs read-only checks of Python, Tkinter, dependencies, project files, configuration, and local environments; failures include repair guidance.",
})

TOOLTIPS_IT.update({
    "PHOTO-CAT": "PHOTO-CAT valuta a livello di catalogo il rischio di contaminazione e seleziona i target. Inizia da File e colonne, continua con Impostazioni di ricerca e termina con Opzioni di esecuzione.",
    "Photometric Contamination Analyzer Tool - configure the pipeline and run every command.": "Questa finestra configura l'intero flusso: prepara l'indice, interroga i target, esamina i risultati, valida le previsioni e crea prodotti riproducibili.",
    "Switch to light mode": "Cambia soltanto l'aspetto della GUI usando un tema chiaro. Valori scientifici, configurazione, file e palette dei grafici non cambiano.",
    "Switch to dark mode": "Cambia soltanto l'aspetto della GUI usando un tema scuro. Valori scientifici, configurazione, file e palette dei grafici non cambiano.",
    "Configure pipeline": "Queste sezioni definiscono catalogo, colonne di coordinate e magnitudine, geometria di ricerca, modello di contaminazione e fasi da eseguire.",
    "Files & columns": "Apre i dati di input. Seleziona catalogo e target, poi verifica che ogni colonna corrisponda esattamente all'intestazione CSV.",
    "Search settings": "Apre apertura, raggio di influenza, contrasto di magnitudine, bande fotometriche e modello di pesatura radiale.",
    "Run options": "Apre i controlli che decidono se costruire l'indice, interrogare i target, conservare ID mancanti e sostituire una pipeline attiva.",
    "Results": "Questi comandi esaminano, classificano, rappresentano, documentano, esportano o validano un JSON di risultati.",
    "Catalogue": "Questi comandi documentano la provenienza del catalogo o uniscono stelle brillanti supplementari prima della costruzione.",
    "Diagnostics": "Controlli dello stato dell'ambiente che non modificano indici o risultati scientifici.",
    "Summarize": "Apre lo strumento che calcola conteggi e statistiche aggregate di contaminazione da un JSON di risultati.",
    "Screen / rank": "Classifica i punteggi di rischio e assegna decisioni accetta, revisiona, respingi o non risolto tramite soglie esplicite.",
    "Plot (SVG)": "Apre i grafici diagnostici. SVG non richiede un backend; matplotlib supporta ulteriori formati.",
    "Provenance": "Registra checksum, righe, colonne, intervalli e query ADQL opzionale usata per creare il catalogo.",
    "Files and columns": "Definisce le tabelle lette da PHOTO-CAT e associa le intestazioni a ID sorgente, coordinate celesti e magnitudine.",
    "Catalog column names": "Queste quattro intestazioni distinguono maiuscole e minuscole e forniscono ID, ascensione retta, declinazione e magnitudine.",
    "Targets column name": "Imposta l'intestazione del CSV target contenente gli ID sorgente. Normalmente resta source_id.",
    "Model mode": "Scegli top_hat per l'inclusione semplice, modalità gaussiane per una PSF circolare approssimata o radial_weight per una curva calibrata.",
    "Advanced performance settings": "Blocco e checkpoint influenzano velocità, RAM, scritture e ripresa, ma non la selezione scientifica prevista.",
    "Enable advanced settings": "Sblocca dimensione del blocco e frequenza dei checkpoint. Lascialo disabilitato salvo necessità di memoria o scala.",
    "Options": "Seleziona fasi e comportamento per target mancanti, separazioni salvate, CSV grandi e avvii ripetuti.",
    "Use manual list": "Usa gli ID nei Target manuali al posto di un CSV separato. Gli ID devono esistere nell'indice costruito.",
    "Replace running pipeline when Save + run is clicked": "Chiude la precedente pipeline avviata dalla GUI prima di lanciarne un'altra, evitando due elaborazioni pesanti accidentali.",
    "Tool output": "Mostra stdout e stderr degli strumenti. Pulire questa area non elimina report, grafici, JSON, indici o log salvati.",
    "Clear": "Pulisce soltanto la console visibile. Report, grafici, JSON, indici e log restano sul disco.",
    "Help": "Apre una guida breve con procedura consigliata, requisiti degli input e spiegazione dei modelli di contaminazione.",
    "Load example config": "Sostituisce i valori del modulo con l'esempio incluso. Controlla i percorsi prima di salvare o eseguire.",
    "Save config.yaml": "Valida il modulo e salva lingua, percorsi, impostazioni scientifiche e scelte di esecuzione senza avviare la pipeline.",
    "Save + run pipeline": "Valida e salva config.yaml, poi avvia build/query in una console separata. Cataloghi grandi possono richiedere tempo e spazio.",
    "Browse...": "Apre la selezione di file o cartelle. Il percorso resta modificabile prima del salvataggio.",
    "Add file...": "Aggiunge un altro percorso all'elenco senza rimuovere quelli già presenti.",
    "Quick help": "Procedura breve per chi inizia. Usa i tooltip dei campi per scegliere i valori scientifici.",
    "Default Gaia-like names are pre-filled. Change them only if your CSV headers are different. The names must match the catalog CSV exactly, including uppercase/lowercase.": "Mantieni i nomi Gaia quando esistono nel CSV. Una differenza come RA invece di ra impedisce il caricamento: confrontali con la prima riga.",
    "Default target column is source_id. Change it only if your targets CSV uses another header. This is case-sensitive. Manual targets ignore this field.": "Associa l'identificatore della tabella target all'ID del catalogo. Non seleziona la colonna ID del catalogo, configurata separatamente.",
    "One band=catalog_column per line, for example gaia_bp=phot_bp_mean_mag. gaia_g is always mapped to the catalog magnitude column above. Extra bands can then be requested in Search settings > Contamination bands.": "Salva bande aggiuntive solo se le colonne esistono e contengono numeri compatibili. Ogni banda richiesta deve essere prima inclusa nell'indice.",
    "Optional. Leave Targets CSV empty/null to use this source_id list instead. Use one source_id per line, or separate them with commas.": "Adatto a pochi target. Per selezioni grandi un CSV è più facile da verificare e riprodurre.",
    "The aperture radius defines the extraction/screening circle. The influence radius can be larger when a weighted PSF model should include leakage from nearby sources outside that aperture. Both must be equal to or smaller than the max build radius.": "Scegli i raggi in arcosecondi. Il raggio di costruzione è il limite dei dati: una query più ampia non recupera vicini mai indicizzati.",
    "top_hat keeps the historical catalogue/aperture flux estimate. gaussian_psf and gaussian_aperture need a Gaussian FWHM. radial_weight needs a CSV of sep_arcsec,weight.": "Usa top_hat per screening geometrico preliminare. Usa un modello pesato solo se FWHM o curva radiale rappresentano ragionevolmente lo strumento.",
    "Leave these locked unless you know what you are doing. Wrong values can make the tool slower, use too much RAM, write too often to disk, or make long runs harder to resume safely.": "Il blocco bilancia memoria e velocità; il checkpoint bilancia scritture e lavoro perso dopo un'interruzione. Prova prima su un sottoinsieme.",
    "Enabled: the previous pipeline window opened by this GUI is closed before a new run starts. Disabled: each Save + run opens a separate pipeline window.": "Abilita su normali workstation per evitare due build in competizione per RAM e disco. Disabilita solo per configurazioni indipendenti intenzionali.",
    "Output from Results / Catalogue / Benchmark / Diagnostics commands appears here.": "Mostra percorsi salvati, riepiloghi, avvisi ed errori. L'avanzamento build/query appare nella console separata della pipeline.",
    "Recommended workflow:\n1. Select Catalog CSV in Files & columns.\n2. Check that Targets CSV and output folders were auto-filled correctly.\n3. Leave the Gaia-like column names unchanged unless your CSV uses different headers.\n4. Click Save + run pipeline.\n5. Use the Results and Catalogue panels on the output JSON afterwards.": "Seguire quest'ordine evita gran parte degli errori di percorso e colonna. Prova l'esempio incluso prima di un catalogo grande.",
    "Summarize a PHOTO-CAT query result JSON as text, JSON, or CSV.": "Usa text per leggere, JSON per automazione o CSV per una riga di statistiche. Non ricalcola la contaminazione.",
    "Rank targets by a contamination metric and assign accept / review / reject decisions.": "Scegli soglie adatte alla missione. Le decisioni sono screening, non prova che la fotometria estratta sia priva di bias.",
    "Write a plot from a PHOTO-CAT query result JSON.": "Crea una relazione diagnostica dai risultati salvati. Le etichette dei grafici restano in inglese.",
    "Generate contaminant-count and separation distributions, and the RA/Dec contamination sky map.": "Crea prodotti coordinati da un risultato e registra impostazioni e checksum in un manifest.",
    "Write an HTML or Markdown report from a PHOTO-CAT query result JSON.": "Crea un riepilogo portabile. HTML incorpora grafici SVG; Markdown è comodo per repository e revisioni.",
    "Export target-result rows to CSV or Parquet.": "CSV è compatibile quasi ovunque; Parquet conserva meglio i tipi ed è spesso più compatto e veloce.",
    "Compare PHOTO-CAT predictions with an external reference contamination table.": "Abbina per ID e calcola residui. Prima di interpretarli verifica che percentuale e apertura abbiano la stessa definizione.",
    "Capture provenance metadata for a catalogue CSV.": "Registra identità e metadata per citare, controllare variazioni e riprodurre la selezione del catalogo.",
    "Merge a Gaia-like base catalogue with a supplemental bright-star table.": "Usa prima della build se il catalogo può omettere sorgenti sature o molto brillanti. Controlla la preferenza dei duplicati.",
    "Run selected pipeline stages using the current config and write benchmark metadata JSON. Uses the config.yaml saved by this GUI unless you pick another config file.": "Confronta configurazioni equivalenti su una macchina libera e registra insieme dimensione, raggio, hardware, tempo e memoria.",
    "Render one or more benchmark JSON captures as a Markdown or CSV table.": "Usa Markdown per una tabella leggibile e CSV per altre analisi. Confrontare raggi o cataloghi diversi può essere fuorviante.",
    "Generate reproducible summaries, plots, reports, and a manifest from configs and/or result JSONs.": "Raccoglie input e prodotti con versioni e checksum. Abilita la riesecuzione solo se vuoi lanciare nuovamente tutte le configurazioni.",
    "Run environment and configuration diagnostic checks.": "Controlla in sola lettura Python, Tkinter, dipendenze, file, configurazione e ambienti locali, indicando come riparare i problemi.",
})


def normalize_language(language: str | None) -> str:
    """Return a supported two-letter language code."""
    normalized = str(language or "").strip().lower().replace("-", "_")
    if (normalized.startswith("it")):
        return "it"
    return "en"


def set_language(language: str | None) -> str:
    """Set the process-local language and propagate it to child processes."""
    global _language
    _language = normalize_language(language)
    os.environ[LANGUAGE_ENVIRONMENT] = _language
    return _language


def get_language() -> str:
    return _language


def language_from_config(config_path: str | Path | None) -> str | None:
    """Read only the optional interface language without invoking runtime validation."""
    if (config_path is None):
        return None
    path = Path(config_path)
    if (not path.is_file()):
        return None
    try:
        source = path.read_text(encoding="utf-8")
        if (yaml is None):
            in_interface = False
            for raw_line in source.splitlines():
                stripped = raw_line.strip()
                if (not raw_line.startswith((" ", "\t"))):
                    in_interface = stripped == "interface:"
                elif (in_interface and stripped.startswith("language:")):
                    return stripped.split(":", 1)[1].strip().strip("'\"")
            return None
        document = yaml.safe_load(source) or {}
    except OSError:
        return None
    except Exception as error:
        if (yaml is not None and isinstance(error, yaml.YAMLError)):
            return None
        raise
    if (not isinstance(document, dict)):
        return None
    interface = document.get("interface")
    return interface.get("language") if isinstance(interface, dict) else None


def initialize_language(config_path: str | Path | None = None, explicit: str | None = None) -> str:
    """Select explicit, environment, config, then English language precedence."""
    selected = explicit or os.environ.get(LANGUAGE_ENVIRONMENT) or language_from_config(config_path) or "en"
    return set_language(selected)


def tr(text: Any, **values: Any) -> str:
    """Translate user-visible text while preserving technical values and formatting."""
    source = str(text)
    if (_language != "it"):
        return source.format(**values) if values else source
    exact = ITALIAN.get(source)
    if (exact is not None):
        return exact.format(**values) if values else exact
    if (values):
        source = source.format(**values)
    if (source == ""):
        return source
    if ("\n" in source):
        return "\n".join(tr(line) for line in source.splitlines())
    translated = source
    for english, italian in ITALIAN_FRAGMENTS:
        translated = translated.replace(english, italian)
    return translated


def tooltip_for(label: str, widget_kind: str = "control") -> str:
    """Return beginner guidance for every control, with detailed astronomy help where available."""
    catalog = TOOLTIPS_IT if _language == "it" else TOOLTIPS_EN
    if label in catalog:
        return catalog[label]
    translated_label = tr(label)
    if (_language == "it"):
        if (widget_kind == "button"):
            return f"Esegue «{translated_label}». Prima controlla i campi della sezione corrente; risultati, percorsi salvati ed eventuali errori appariranno nella console degli strumenti."
        if (widget_kind == "section"):
            return f"Sezione «{translated_label}»: raccoglie impostazioni o strumenti collegati. Aprila e completa i campi dall'alto verso il basso; passa sui singoli valori per dettagli specifici."
        return f"Imposta o controlla «{translated_label}». Se non conosci il significato del valore, mantieni il predefinito e prova prima sui dati di esempio; il controllo viene validato prima dell'esecuzione."
    if (widget_kind == "button"):
        return f"Runs “{label}”. Review the current section first; saved paths, results, and expected errors will appear in the tool console."
    if (widget_kind == "section"):
        return f"The “{label}” section groups related settings or tools. Open it and work from top to bottom; hover over individual values for specific guidance."
    return f"Set or review “{label}”. If its meaning is unfamiliar, keep the default and test with the example data first; PHOTO-CAT validates the control before execution."
