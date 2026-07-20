# Configurazione

PHOTO-CAT salva la configurazione di esecuzione nel file `config.yaml` nella cartella principale.

Il modo consigliato per modificare questo file è usare la configurazione grafica aperta da `START_WINDOWS.bat` o `START_UNIX.sh`.

## Sezioni principali

La configurazione controlla:

- lingua dell'interfaccia (`en` o `it`)
- percorso del catalogo di input
- percorso del file target o target manuali
- mapping delle colonne del catalogo
- cartella di output
- percorsi dell’indice dei vicini
- opzioni della fase di build
- opzioni della fase di query
- modalità di esecuzione

## Lingua dell'interfaccia

Il valore `interface.language` seleziona la lingua mostrata all'utente:

```yaml
interface:
  language: it  # en oppure it
```

Si applica a GUI, tooltip, guida CLI, messaggi della console, avvisi ed errori previsti. Il selettore della lingua nella GUI aggiorna subito l'interfaccia e salva la scelta nella configurazione. Le etichette scientifiche dei grafici restano intenzionalmente in inglese, per mantenere le figure coerenti fra esecuzioni e adatte alla pubblicazione internazionale.

## Gestione percorsi del catalogo

Quando viene selezionato un CSV catalogo nella GUI, PHOTO-CAT può inizializzare percorsi collegati come file target, cartella output/indice e cartella indice per la query.

I valori restano modificabili prima dell’esecuzione.

## Fase di build

La fase di build crea un indice dei vicini dal catalogo.

Usala quando cambiano catalogo, colonne coordinate, raggio di ricerca o cartella output/indice.

Colonne opzionali di magnitudine multi-banda possono essere salvate nell'indice
per confronti successivi di screening:

```yaml
build_neighbors_index:
  io:
    magnitude_columns:
      gaia_g: phot_g_mean_mag
      gaia_bp: phot_bp_mean_mag
      gaia_rp: phot_rp_mean_mag
```

`gaia_g` usa per impostazione predefinita la colonna `phot_g_mean_mag`
configurata. Le bande aggiuntive vengono scritte come array numerici e
registrate in `index_manifest.json`.

## Fase di query

La fase di query legge un indice esistente e processa i target selezionati.

Usala quando l’indice esiste già e devi solo interrogare target o modificare opzioni di query.

Il modello di contaminazione predefinito è `top_hat`, che conserva la stima
storica catalogo/apertura. In alternativa si può selezionare una PSF gaussiana
circolare 2D, che pesa ogni sorgente secondo il decadimento radiale del flusso:

```yaml
query_contamination_from_index:
  settings:
    field_of_view_arcsec: 47.0       # apertura di estrazione/screening
    contamination_bands: [gaia_g, gaia_bp, gaia_rp]
    contamination_model:
      mode: gaussian_psf
      gaussian_fwhm_arcsec: 2.0      # larghezza a metà altezza della PSF
      influence_sigma: 5.0           # quanti sigma di leakage considerare
```

Con `gaussian_psf` ogni sorgente contribuisce con `exp(-r^2 / 2*sigma^2)` del
proprio flusso a distanza angolare `r` dal centro dell'apertura, dove
`sigma = gaussian_fwhm_arcsec / 2.3548`.

Il raggio esterno di influenza **non si configura direttamente**: si ricava come
`sigma * influence_sigma`, così il raggio di ricerca segue l'ottica invece di
essere un numero impostato a mano. Con i valori qui sopra `sigma = 0.849"` e il
raggio di influenza è `4.25"`. Può legittimamente risultare più piccolo del
raggio di apertura: una PSF stretta smette di contribuire leakage ben dentro una
circonferenza di estrazione ampia. Se supera il raggio di build dell'indice,
PHOTO-CAT ricalcola i vicini direttamente dal catalogo per i target interrogati,
operazione più lenta per target.

`top_hat` non ha una scala PSF, quindi cerca solo entro il raggio di apertura.

Oltre ai pesi, `gaussian_psf` riporta anche metriche integrate sull'apertura
(`effective_target_flux`, `effective_contaminating_flux`, `contamination_ratio`,
`target_purity`), che integrano la gaussiana circolare sull'apertura disassata.

Resta un'approssimazione a livello di catalogo per lo screening, salvo che la
FWHM provenga da una calibrazione PSF specifica dello strumento.

### Trasformazioni empiriche nella banda di missione

Un profilo YAML opzionale e versionato può derivare una magnitudine di missione
da bande di catalogo memorizzate:

```yaml
query_contamination_from_index:
  settings:
    bandpass_transform_file: examples/reproducibility/bandpass_transform_example.yaml
```

Il profilo definisce `output_band`, `base_band`, due `color_bands`, i
`coefficients` del polinomio, limiti calibrati di colore/magnitudine, una
politica `out_of_range` e il riferimento della calibrazione. La convenzione è:

```text
m_output = m_base + c0 + c1*colore + c2*colore^2 + ...
colore = m_color_band_1 - m_color_band_2
```

Le bande richieste devono essere state memorizzate tramite `magnitude_columns`
durante la build. `out_of_range: null` esclude valori non calibrati;
`out_of_range: extrapolate` li conserva ma marca ogni target interessato come
`extrapolated`. Profilo e checksum SHA-256 vengono copiati nei metadata della
query. Si tratta di una trasformazione empirica di colore, non di integrazione
della banda su una distribuzione spettrale di energia.

## Salva e avvia la pipeline

`Salva e avvia la pipeline` scrive le impostazioni correnti della GUI in `config.yaml`, poi avvia la pipeline in una console separata.

La console della pipeline mostra il progresso e il percorso finale dell’output.


## Validazione prima dell’elaborazione

Prima di avviare una build o una query costosa, PHOTO-CAT valida la struttura della configurazione e i tipi delle principali impostazioni. I raggi di ricerca e il campo visivo devono essere positivi, le dimensioni di chunk e buffer devono essere interi positivi e le impostazioni booleane devono essere true o false.

I percorsi dei file e le intestazioni CSV vengono poi controllati dalla fase build o query interessata, così il messaggio di errore può identificare l’input coinvolto.

## Override CLI

Ogni valore in `config.yaml` può anche essere sovrascritto da riga di comando per una singola esecuzione.

Esempio:

```bash
photo-cat run --config config.yaml --field-of-view-arcsec 60 --delta-mag 4
```

Il file YAML non viene modificato permanentemente. Gli override CLI vengono derivati per un solo comando, mentre la configurazione originale caricata rimane invariata. L'interpretazione e la validazione della configurazione non creano cartelle di output; le risorse runtime di build e query vengono create solo dopo una validazione riuscita. Per tutti i flag di override disponibili e gli esempi, vedi [Uso da riga di comando](Command-line_IT.md).
