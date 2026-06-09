# Dati di input

PHOTO-CAT usa file CSV per il catalogo e, opzionalmente, per i target.

## Catalogo CSV

Il catalogo deve contenere colonne per:

- source ID
- ascensione retta
- declinazione
- magnitudine fotometrica

I nomi predefiniti in stile Gaia sono:

- `source_id`
- `ra`
- `dec`
- `phot_g_mean_mag`

## CSV target

Un CSV target può essere usato per indicare le sorgenti da analizzare.

Il file deve contenere una colonna source ID che corrisponda agli ID presenti nel catalogo o nell’indice creato.

## Target manuali

In alternativa, i target possono essere inseriti manualmente nella configurazione come lista di source ID.

## Nomi colonne

I nomi delle colonne sono case-sensitive e devono corrispondere esattamente all’header del CSV.

Se i tuoi file usano nomi diversi, cambiali nella configurazione grafica prima di eseguire la pipeline.

## File di esempio

La cartella `data/` contiene piccoli file CSV di esempio per verificare rapidamente che il progetto funzioni.
