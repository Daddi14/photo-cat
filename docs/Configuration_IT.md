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

### Conversione fotometrica di banda

Per default la contaminazione è stimata nella banda del catalogo. Una conversione
opzionale la stima invece in una banda di missione:

```yaml
query_contamination_from_index:
  settings:
    photometric_conversion:
      output_band: tess          # un filtro integrato, una banda con relazione
                                 # Gaia pubblicata (johnson_v, 2mass_ks, ...),
                                 # o "custom"
      conversion_method: blackbody   # blackbody | gaia_empirical | auto | phoenix
      filter_file:               # serve solo quando output_band è custom
      catalog: gaia_dr3
```

La banda di uscita selezionata diventa la banda di riferimento per il taglio in
differenza di magnitudine, la lista dei contaminanti, le frazioni di flusso
principali, i conteggi e le metriche PSF. Se quella banda esatta è già presente
nell'indice (per esempio `gaia_bp` o `gaia_rp`), PHOTO-CAT usa direttamente le
magnitudini nominali del catalogo e non esegue alcuna conversione.

Altrimenti la conversione viene eseguita. In entrambi i casi servono le bande
colore del catalogo (BP, RP) memorizzate con `magnitude_columns` durante la build.
PHOTO-CAT carica automaticamente le bande richieste: non è necessario ripeterle in
`contamination_bands`.

#### Metodi di conversione

| `conversion_method` | Cosa fa | Quando usarlo |
| --- | --- | --- |
| `blackbody` (default) | Conversione approssimata basata sulla SED: il colore BP-RP fornisce una temperatura equivalente di corpo nero e quello spettro viene integrato nella curva di trasmissione della banda. | Qualsiasi banda con una curva di trasmissione, comprese le bande di missione e i profili forniti dall'utente. |
| `gaia_empirical` | Trasformazione empirica basata sul colore, calibrata sulla fotometria Gaia per uno specifico sistema fotometrico pubblicato. Non assume alcun modello spettrale. | I sistemi fotometrici per cui Gaia pubblica relazioni, entro il loro intervallo di colore calibrato. |
| `auto` | Usa la trasformazione empirica Gaia quando esiste una relazione calibrata e la sorgente rientra nel suo intervallo di validità; altrimenti ricade sulla conversione blackbody. | Cataloghi misti, in cui alcune sorgenti cadono fuori dall'intervallo di colore calibrato. |
| `phoenix` | Selezionabile ma richiede una griglia esterna di spettri modello; erra chiaramente finché non viene fornita. | Non ancora disponibile. |

Con `blackbody`, `m_out = m_anchor - 2.5*log10(R)` con
`R = F_out(Teff)/F_anchor(Teff)`. Poiché la contaminazione usa solo rapporti di
flusso nella stessa banda, lo zero-point di uscita si cancella e si mantiene
quello della banda di ancoraggio.

Con `gaia_empirical` si valuta direttamente il polinomio pubblicato
`G - X = sum(c_n * (BP-RP)^n)`, quindi `X = G - polinomio(BP-RP)`. Le relazioni,
i loro intervalli di validità in colore e la dispersione pubblicata provengono
dalla documentazione Gaia DR3, Sez. 5.5.1, Tabelle 5.9-5.10 (Riello et al. 2021,
A&A 649, A3). Nulla viene estrapolato: una sorgente il cui colore cade fuori
dall'intervallo pubblicato viene riportata con
`conversion_status: colour_outside_valid_range` e lasciata non convertita, e una
banda senza relazione pubblicata viene rifiutata già in fase di configurazione.

Non esiste alcuna relazione Gaia verso le bande di missione. Ariel, MAUVE, TESS,
CHEOPS e i filtri SVO si convertono con `blackbody` (o con `auto`, che lo
seleziona automaticamente per loro); `gaia_empirical` su una banda simile è un
errore, non una scelta della relazione più vicina.

#### Bande di uscita

`output_band` può essere:

- la chiave di un filtro integrato: `gaia_g`, `gaia_bp`, `gaia_rp`, `tess`,
  `cheops`, `mauve` e i canali Ariel `ariel_fgs1`, `ariel_fgs2`, `ariel_visphot`,
  `ariel_airs_ch0`, `ariel_airs_ch1`, `ariel_nirspec`;
- una banda con relazione Gaia pubblicata: `johnson_b`, `johnson_v`, `johnson_r`,
  `cousins_i` (Johnson-Cousins), `2mass_j`, `2mass_h`, `2mass_ks` (2MASS),
  `sdss_g`, `sdss_r`, `sdss_i`, `sdss_z` (SDSS12), `hipparcos_hp` (Hipparcos),
  `tycho_bt`, `tycho_vt` (Tycho-2). Sono accettate anche le forme brevi `b`, `v`,
  `r`, `i`, `j`, `h`, `ks`, `z`, `hp`, `bt`, `vt`; `r` e `i` indicano le bande
  Johnson-Cousins e le bande SDSS mantengono il prefisso perché una `g` isolata
  si leggerebbe come la G di Gaia;
- `custom` con un `filter_file`.

Una banda può comparire in entrambi gli elenchi. Perché `auto` abbia un fallback
blackbody serve una curva di trasmissione installata per quella banda: senza,
le sorgenti fuori dall'intervallo di colore della relazione restano non convertite
e vengono riportate come tali.

I filtri arrivano da due cartelle, lette insieme. Le curve ufficiali distribuite
con la release (Gaia, TESS, CHEOPS, MAUVE e i canali Ariel) stanno dentro il
package. Le curve scaricate e quelle aggiunte dall'utente stanno nella cartella
dati dell'utente, dove un aggiornamento o una reinstallazione non può cancellarle:

| Piattaforma | Libreria filtri utente |
| --- | --- |
| Windows | `%APPDATA%\photo-cat\filters` |
| macOS | `~/Library/Application Support/photo-cat/filters` |
| Linux | `$XDG_DATA_HOME/photo-cat/filters` (default `~/.local/share/photo-cat/filters`) |

Imposta `PHOTO_CAT_FILTERS_DIR` per spostare la libreria utente. Aggiungere una
missione significa solo mettere lì la sua curva ufficiale come
`<Missione>/<banda>.dat`. Un filtro lasciato dentro il package da una versione
precedente continua a funzionare, perché entrambe le cartelle vengono scandite; se
la stessa chiave di banda esiste in entrambe vince la libreria utente, così una
curva installata localmente sostituisce una distribuita. Altri filtri si possono
scaricare dal SVO Filter Profile Service direttamente nella GUI (il pannello
"Scarica un filtro da SVO" sceglie una facility, ne elenca i filtri e ne scarica
uno nella libreria utente) o con `photo_cat.photometry.svo.download_filter`.

Il percorso blackbody è una stima approssimata a livello di catalogo per lo
screening: le stelle reali non sono corpi neri e la temperatura efficace riportata
è una temperatura di colore equivalente di corpo nero, non una Teff fisica. Il
percorso empirico non riporta alcuna temperatura, perché non ne deriva nessuna.
Il filtro di uscita con il suo checksum SHA-256, la relazione usata con i suoi
coefficienti e la dispersione pubblicata, e i conteggi per run di quante sorgenti
ha convertito ciascun metodo finiscono tutti nei metadata della query.

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
