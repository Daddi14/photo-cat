<!--
SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
SPDX-License-Identifier: GPL-3.0-only
-->

# Libreria filtri PHOTO-CAT

Curve di trasmissione usate dalla conversione fotometrica di banda
(`photo_cat.photometry`). L'albero è auto-rilevato: aggiungere una missione
significa solo mettere un file nel formato corretto in una nuova cartella, senza
modifiche al codice.

## Struttura

```
filters/
  <Missione>/<banda>.dat
```

- `Gaia/BP.dat` si indirizza con la chiave di banda `gaia_bp`.
- Una missione a banda singola il cui file si chiama `response.dat` (o `band`,
  `filter`, `throughput`, o il nome della missione) è indirizzabile anche col
  solo nome della missione, quindi `TESS/response.dat` è selezionabile come
  `output_band: TESS`.

Le chiavi di banda sono in minuscolo, con le sequenze non alfanumeriche ridotte a `_`.

## Formato del file

Due colonne, separate da spazi o virgole:

```
# unit: angstrom            (opzionale: nm | angstrom | micron)
# transmission: fraction    (opzionale: fraction | percent)
wavelength   transmission
3250         3.87e-05
3260         1.76e-04
...
```

- Lo stesso formato serve per un filtro personalizzato dell'utente
  (`output_band: custom`, `filter_file: percorso`).
- Se manca l'header `# unit:`, l'unità è dedotta dall'ordine di grandezza della
  lunghezza d'onda (`<100` micron, `<3000` nm, altrimenti angstrom). Se manca
  `# transmission:`, i valori sopra ~1.5 sono trattati come percentuale. Gli
  header rimuovono ogni ambiguità; includili nel dubbio.

## Curve incluse

| File | Chiave di banda | Provenienza |
|------|-----------------|-------------|
| `Gaia/G.dat`          | `gaia_g`    | ufficiale — SVO `GAIA/GAIA3.G`   |
| `Gaia/BP.dat`         | `gaia_bp`   | ufficiale — SVO `GAIA/GAIA3.Gbp` |
| `Gaia/RP.dat`         | `gaia_rp`   | ufficiale — SVO `GAIA/GAIA3.Grp` |
| `TESS/response.dat`   | `tess`      | ufficiale — SVO `TESS/TESS.Red`     |
| `CHEOPS/response.dat` | `cheops`    | ufficiale — SVO `CHEOPS/CHEOPS.band` |
| `MAUVE/response.dat`  | `mauve`     | ufficiale — curva di area efficace normalizzata |
| `Ariel/FGS1.dat`      | `ariel_fgs1`     | ufficiale — Ariel FGS1 |
| `Ariel/FGS2.dat`      | `ariel_fgs2`     | ufficiale — Ariel FGS2 |
| `Ariel/VISPhot.dat`   | `ariel_visphot`  | ufficiale — Ariel VISPhot |
| `Ariel/AIRS-CH0.dat`  | `ariel_airs_ch0` | ufficiale — Ariel AIRS-CH0 |
| `Ariel/AIRS-CH1.dat`  | `ariel_airs_ch1` | ufficiale — Ariel AIRS-CH1 |
| `Ariel/NIRSpec.dat`   | `ariel_nirspec`  | ufficiale — Ariel NIRSpec |

Le curve Gaia, TESS e CHEOPS sono risposte ufficiali dal SVO Filter Profile
Service (http://svo2.cab.inta-csic.es/theory/fps/). MAUVE è derivata dalla sua
curva ufficiale di area efficace, normalizzata al picco (nel rapporto di flusso
entra solo la forma spettrale, quindi l'area assoluta si cancella). I canali Ariel
sono curve di trasmissione ufficiali. La provenienza è registrata nell'header di
ogni file. Le bande Gaia servono anche al motore colore→temperatura.

Vengono forniti solo filtri ufficiali. Un file può dichiarare `# provenance:`
nel suo header; una curva marcata `nominal-approximate` (per esempio un
segnaposto fornito a mano) viene segnalata nei metadata e avvisata a runtime,
così non viene mai scambiata per una risposta strumentale misurata.

Altri filtri si possono scaricare dal SVO Filter Profile Service direttamente
nella GUI (pannello "Scarica un filtro da SVO") o via codice con
`photo_cat.photometry.svo.download_filter`. Vengono salvati in questo albero e
diventano subito selezionabili.

## Aggiungere una missione

Scarica la curva di trasmissione ufficiale (per esempio dal SVO Filter Profile
Service) per la banda di missione che ti serve, salvala in questo formato in
`filters/<Missione>/<banda>.dat` e diventa subito selezionabile come
`output_band: <missione>` o `<missione>_<banda>`. PHOTO-CAT non include curve di
missione inventate; usa la risposta strumentale pubblicata.
