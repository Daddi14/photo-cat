# PHOTO-CAT - Photometric Contamination Analyzer Tool

PHOTO-CAT è un tool Python con launcher semplice per creare un indice dei vicini da un catalogo fotometrico CSV e interrogare possibili contaminazioni per sorgenti target.

Il progetto è pensato per utenti non tecnici: scaricano lo ZIP della release, lo estraggono e avviano un solo file.

## Avvio rapido

Scarica lo ZIP della release, estrailo, poi avvia il file corretto per il tuo sistema operativo:

```text
Windows: doppio click su START_WINDOWS.bat
macOS:   doppio click su START_MACOS.command
Linux:   esegui ./START_LINUX.sh
```

Il launcher gestisce il flusso base:

```text
controlla/installa Python dove possibile -> crea .venv -> installa librerie -> apre GUI -> esegue pipeline
```

## Cosa fa automaticamente la GUI

Quando scegli `Catalog CSV`, la GUI imposta automaticamente:

```text
Targets CSV         = stesso file del Catalog CSV
Output/index folder = cartella_del_catalog/output
Query index folder  = stesso Output/index folder
```

Poi clicca `Save + run`.

## Colonne richieste

I nomi colonna predefiniti sono in stile Gaia:

```text
Catalog CSV: source_id, ra, dec, phot_g_mean_mag
Targets CSV: source_id
```

Puoi modificarli nella GUI se il tuo CSV usa header diversi.

I nomi colonna sono **case-sensitive**. Esempi:

```text
ra è diverso da RA
Dec è diverso da dec
phot_g_mean_mag è diverso da PHOT_G_MEAN_MAG
```

Quindi i nomi scritti nella GUI devono combaciare esattamente con quelli nel CSV.

## Target manuali

Puoi svuotare `Targets CSV` e inserire source_id manuali nella sezione `Manual targets`. La GUI salverà:

```yaml
TARGETS_INPUT: null
targets:
  - 123456789012345678
  - 987654321098765432
```

## Note Windows dark mode

Su Windows, la GUI prova a rilevare automaticamente la modalità scura delle app e applica un tema scuro. Le finestre di dialogo di sistema possono comunque restare dipendenti dal tema nativo di Windows.

## Pubblicazione

Le istruzioni per pubblicare il progetto su GitHub e creare una release sono in:

```text
docs/PUBLISHING.md
```
