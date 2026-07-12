# Script launcher

Questa cartella contiene script di supporto usati dai launcher principali nella cartella root.

Gli utenti normali dovrebbero avviare solo i file starter nella cartella root:

- `START_WINDOWS.bat`
- `START_UNIX.sh`

## Helper principali

- `start_windows.ps1`, logica principale del launcher Windows.
- `start_linux_macos.sh`, logica principale del launcher macOS/Linux.
- `run_pipeline_windows.bat`, apre la pipeline in una console Windows separata.
- `run_pipeline_unix.sh`, esegue la pipeline da macOS/Linux dopo `Save and run`.
- `fix_console_window.ps1`, regola la dimensione della console Windows.

## Helper di compatibilità

- `install_windows.bat`
- `configure_windows.bat`
- `run_windows.bat`
- `install_linux_macos.sh`
- `configure_linux_macos.sh`
- `run_linux_macos.sh`

Sono forniti per workflow avanzati/manuali. La maggior parte degli utenti non ne ha bisogno.

## Aggiornamento dell'helper runtime

I launcher fissano la versione dell'helper `uv` e verificano il digest SHA-256
ufficiale prima dell'estrazione. Quando si aggiorna `UV_VERSION`/`UvVersion`,
aggiornare tutti i digest di piattaforma dalla stessa release upstream immutabile
e mantenere allineati i test di sicurezza dei launcher.
