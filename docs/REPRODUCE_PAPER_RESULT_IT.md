<!-- SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors -->
<!-- SPDX-License-Identifier: GPL-3.0-only -->
# Riprodurre i risultati del paper

[English](REPRODUCE_PAPER_RESULT.md) · [Italiano](REPRODUCE_PAPER_RESULT_IT.md)

Questa guida per principianti parte dal download di un catalogo Gaia DR3, esegue la pipeline PHOTO-CAT e crea i grafici coordinati della contaminazione tramite l'interfaccia grafica.

## Cosa riproduce questa procedura

La procedura crea il JSON dei risultati PHOTO-CAT corrente e questi prodotti da pubblicazione:

- distribuzione del numero di contaminanti;
- distribuzione delle separazioni angolari;
- mappa di contaminazione in AR/Dec;
- manifest JSON con impostazioni, percorsi, checksum e versione PHOTO-CAT.

Per ottenere valori identici a una tabella o statistica pubblicata servono anche la stessa release PHOTO-CAT, release Gaia, selezione dei target, apertura, contrasto di magnitudine e configurazione usati nell'analisi. Le query ADQL seguenti applicano soltanto le selezioni dichiarate sulla magnitudine G; non aggiungono quality cut astrometrici o fotometrici.

## Prima di iniziare

Servono:

- una release PHOTO-CAT corrente estratta in una cartella scrivibile;
- Python preparato tramite `START_WINDOWS.bat` o `START_UNIX.sh`;
- spazio libero e memoria sufficienti;
- un browser e accesso al [Gaia ESA Archive ufficiale](https://gea.esac.esa.int/archive/).

La selezione all-sky `0 <= phot_g_mean_mag <= 17` può essere molto grande. Usa un job asincrono del Gaia Archive. Per una query lunga è fortemente consigliato un account Gaia, perché permette di recuperare il job e scaricarlo in seguito. Attualmente l'Archive avvisa che durante l'evoluzione verso Gaia DR4 possono verificarsi instabilità o timeout.

Non aprire e risalvare il catalogo con un foglio di calcolo, salvo poter garantire che i `source_id` a 64 bit restino esatti. Notazione scientifica o arrotondamenti possono impedire l'abbinamento dei target.

## Parte 1 — Scaricare i dati Gaia DR3

### 1. Aprire il Gaia Archive

1. Apri [gea.esac.esa.int/archive](https://gea.esac.esa.int/archive/).
2. Accedi oppure crea un account se vuoi conservare il job lungo nella tua area.
3. Apri l'area di ricerca/query e scegli l'interfaccia ADQL avanzata. Le diciture possono cambiare leggermente; cerca **Advanced (ADQL)** o un'opzione equivalente.

La documentazione Gaia DR3 identifica `gaiadr3.gaia_source` come catalogo principale e offre tutorial per ADQL e l'uso avanzato dell'Archive.

### 2. Preparare la query G=17 del catalogo dei vicini

Usa questa query:

```sql
SELECT gaia.source_id,
       gaia.ra,
       gaia.dec,
       gaia.phot_g_mean_mag,
       gaia.parallax,
       gaia.parallax_error
FROM gaiadr3.gaia_source AS gaia
WHERE phot_g_mean_mag BETWEEN 0 AND 17
```

Significato delle colonne:

- `source_id`: identificatore univoco della sorgente Gaia DR3;
- `ra`, `dec`: posizione celeste in gradi;
- `phot_g_mean_mag`: magnitudine media Gaia G usata da PHOTO-CAT;
- `parallax`, `parallax_error`: scaricate per analisi/provenienza, ma non richieste dal calcolo predefinito della contaminazione.

### 3. Preparare la query separata G=12 dei target

La lista target non deve essere il catalogo G=17. Crea una seconda query Gaia con le stesse colonne e limite G=12:

```sql
SELECT gaia.source_id,
       gaia.ra,
       gaia.dec,
       gaia.phot_g_mean_mag,
       gaia.parallax,
       gaia.parallax_error
FROM gaiadr3.gaia_source AS gaia
WHERE phot_g_mean_mag BETWEEN 0 AND 12
```

I due file hanno ruoli diversi:

- G=17 è il catalogo più profondo dei vicini, usato per trovare possibili sorgenti contaminanti;
- G=12 è il campione più brillante dei target sui quali PHOTO-CAT esegue il controllo della contaminazione.

### 4. Eseguire entrambe le query in modo asincrono

1. Invia il job G=17 con un nome riconoscibile, per esempio `photo_cat_gaia_dr3_g0_g17`.
2. Se l'Archive offre modalità sincrona e asincrona, scegli il job asincrono.
3. Invia il job G=12 come `photo_cat_gaia_dr3_g0_g12`.
4. Apri l'elenco dei job e attendi che entrambi risultino completati.
5. Se uno dei job fallisce o scade, riprova in seguito con un account registrato. Non aggiungere silenziosamente `TOP`, regioni più piccole o altri tagli se vuoi questa selezione esatta; ogni modifica va documentata.

### 5. Scaricare entrambi i CSV

1. Apri il risultato di ogni job completato.
2. Scegli CSV come formato di download.
3. Salva i due file con nomi distinti:

   ```text
   gaia_dr3_g0_g17.csv
   gaia_dr3_g0_g12_targets.csv
   ```

4. Se l'Archive scarica file compressi come `.csv.gz`, estraili in normali `.csv` prima di selezionarli nella GUI.
5. Sposta entrambi i CSV nella cartella `data/` di PHOTO-CAT o in un'altra posizione stabile e scrivibile.
6. Salva le query esatte come `gaia_dr3_g0_g17.adql` e `gaia_dr3_g0_g12_targets.adql`, e annota la data del download.

La prima riga del CSV deve contenere almeno:

```text
source_id,ra,dec,phot_g_mean_mag,parallax,parallax_error
```

Non rinominare le quattro colonne richieste da PHOTO-CAT, salvo modificare anche il mapping nella GUI.

## Parte 2 — Configurare PHOTO-CAT

### 6. Avviare l'interfaccia grafica

- Windows: doppio clic su `START_WINDOWS.bat`.
- macOS/Linux: esegui `sh START_UNIX.sh` dalla cartella del progetto.

Attendi il completamento della preparazione e l'apertura del configuratore PHOTO-CAT.

### 7. Selezionare il catalogo

Apri **File e colonne** e imposta:

- **CSV del catalogo**: il file `gaia_dr3_g0_g17.csv` scaricato;
- **Colonna ID sorgente del catalogo**: `source_id`;
- **Colonna AR del catalogo**: `ra`;
- **Colonna Dec del catalogo**: `dec`;
- **Colonna magnitudine del catalogo**: `phot_g_mean_mag`.

Le colonne di parallasse aggiuntive possono restare nel CSV. PHOTO-CAT legge soltanto le colonne configurate necessarie all'indice.

La selezione del catalogo può compilare automaticamente target e cartelle di output. Controlla ogni percorso prima di eseguire.

### 8. Scegliere i target

Imposta **CSV dei target** sul file separato `gaia_dr3_g0_g12_targets.csv` e mantieni **Colonna ID sorgente dei target** uguale a `source_id`.

Non usare il catalogo G=17 come file dei target. PHOTO-CAT deve costruire i vicini dal catalogo G=17 più profondo e valutare soltanto il campione target G=12 più brillante. Usare G=17 in entrambi i campi cambia la popolazione target e quindi le distribuzioni.

### 9. Controllare le impostazioni di ricerca

Apri **Impostazioni di ricerca** e verifica:

- **Raggio massimo di costruzione** uguale o maggiore dell'apertura desiderata;
- **Raggio dell'apertura di query** corrispondente al risultato richiesto;
- **Raggio esterno di influenza** non superiore al raggio di costruzione;
- **Differenza di magnitudine** uguale alla configurazione dell'analisi;
- **Modello di pesatura della contaminazione** uguale alla configurazione dell'analisi.

Non dedurre l'apertura del paper dal nome del grafico. Registra il valore reale della query. Il valore inserito successivamente in **Grafici da pubblicazione → Apertura** è un metadata del risultato e deve corrispondere alla query che ha prodotto il JSON.

Per un CSV Gaia grande, mantieni **Usa Dask per file CSV molto grandi** abilitato. Lascia blocchi e checkpoint ai valori predefiniti, salvo aver testato alternative sul tuo hardware.

### 10. Controllare le opzioni di esecuzione

Apri **Opzioni di esecuzione** e abilita:

- **Esegui la fase di costruzione**;
- **Esegui la fase di query**.

La costruzione crea l'indice dei vicini riutilizzabile. La query crea il JSON dei target usato dai grafici.

### 11. Salvare ed eseguire

1. Clicca **Salva e avvia la pipeline**.
2. Conferma la finestra.
3. Mantieni aperta la console della pipeline.
4. Attendi che entrambe le fasi terminino correttamente.

Un'elaborazione all-sky può richiedere molto tempo. Le barre dinamiche mostrano avvio, caricamento, costruzione dell'indice, elaborazione target e salvataggio. Una pausa non indica necessariamente un blocco: controlla che tempo trascorso o barra di attività continuino ad aggiornarsi.

Il risultato della query viene scritto in:

```text
<cartella indice>/results/
```

I metadata associati vengono scritti in:

```text
<cartella indice>/results/metadata/
```

## Parte 3 — Creare i grafici dei risultati del paper

### 12. Aprire Grafici da pubblicazione

Torna nella GUI PHOTO-CAT e apri **Risultati → Grafici da pubblicazione**.

Imposta o controlla:

- **JSON dei risultati**: il JSON più recente della pipeline; normalmente la GUI lo compila automaticamente;
- **Apertura, arcsec**: esattamente l'apertura della query rappresentata dal JSON;
- **Cartella di output**: una nuova cartella come `<nome risultato>_publication_plots`;
- **Formato**:
  - `png` per visualizzazione e immagini raster del manoscritto;
  - `pdf` per output vettoriale da pubblicazione;
  - `svg` per output vettoriale modificabile;
- **DPI**: usa `300` o il valore richiesto dalla rivista per PNG. Il DPI incide poco sulla geometria vettoriale PDF/SVG.

### 13. Cliccare Esegui

Clicca **Esegui** nel pannello Grafici da pubblicazione.

La console Output degli strumenti mostra subito una riga animata e il tempo trascorso. Attendi il codice di uscita `0` e i percorsi salvati.

La cartella contiene:

```text
contaminant_count_distribution.<formato>
separation_distribution.<formato>
contamination_sky_map.<formato>
publication_plots_manifest.json
```

Significato:

- **distribuzione del numero di contaminanti**: numero di target per ogni conteggio di contaminanti selezionati;
- **distribuzione delle separazioni**: separazioni angolari grezze dei contaminanti selezionati in bin da un arcosecondo;
- **mappa celeste**: target in AR/Dec classificati per numero di contaminanti con palette colourblind-safe;
- **manifest**: checksum di input/output, apertura, formato, DPI, data di creazione e versione PHOTO-CAT.

Le etichette scientifiche dei grafici restano in inglese indipendentemente dalla lingua della GUI.

## Parte 4 — Verificare e archiviare la riproduzione

Prima di condividere conserva:

- download Gaia originali o procedura documentata per rigenerarli;
- `gaia_dr3_g0_g17.adql`;
- `gaia_dr3_g0_g12_targets.adql`;
- CSV G=17 del catalogo dei vicini e CSV G=12 dei target;
- `config.yaml` usato;
- `index_manifest.json`;
- JSON dei risultati e JSON dei metadata;
- tre grafici generati;
- `publication_plots_manifest.json`;
- versione PHOTO-CAT da `photo-cat --version`;
- data del download e acknowledgement/citazione Gaia DR3.

Conserva i checksum del manifest insieme ai grafici. Se modifichi un grafico o il JSON, il checksum registrato non corrisponde più.

## Comando equivalente

Dopo la creazione del risultato, il pulsante Esegui equivale a:

```bash
photo-cat publication-plots percorso/al/result.json \
  --aperture-arcsec 47 \
  --output-dir percorso/al/result_publication_plots \
  --format png \
  --dpi 300
```

Sostituisci `47` con l'apertura realmente usata dalla query. Non usare il valore di esempio se il risultato è stato prodotto con un'apertura diversa.

## Problemi comuni

### Il job Gaia scade

Usa un job asincrono dopo l'accesso e riprova quando l'Archive è meno occupato. Cambiare la query cambia la selezione e va documentato.

### PHOTO-CAT segnala colonne mancanti

Controlla intestazione e mapping sensibili a maiuscole/minuscole. `ra` e `RA` sono nomi diversi.

### Gli ID sorgente non corrispondono

Usa il CSV originale. I fogli di calcolo possono arrotondare i `source_id` Gaia.

### La build è troppo grande

Mantieni Dask abilitato, chiudi applicazioni che usano molta memoria, verifica lo spazio libero e considera una macchina adatta a un catalogo all-sky. Un catalogo ridotto è utile per imparare, ma non è la stessa riproduzione.

### Grafici da pubblicazione ha selezionato il JSON sbagliato

Scegli il file previsto sotto `<cartella indice>/results/`. Controlla apertura e impostazioni nel JSON dei metadata corrispondente prima di eseguire.

## Riferimenti Gaia ufficiali

- [Gaia ESA Archive](https://gea.esac.esa.int/archive/)
- [Tutorial Gaia Archive DR3](https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_archive/sec_cu9arch_tutorials/)
- [Data model Gaia DR3 `gaia_source`](https://gea.esac.esa.int/archive/documentation/GDR3/Gaia_archive/chap_datamodel/sec_dm_main_source_catalogue/ssec_dm_gaia_source.html)
- [Istruzioni per crediti e citazioni Gaia DR3](https://gea.esac.esa.int/archive/documentation/GDR3/Miscellaneous/sec_credit_and_citation_instructions/)
