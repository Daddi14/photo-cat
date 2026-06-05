# Script launcher

Questa cartella contiene script di supporto usati dai launcher principali nella cartella root.

Gli utenti finali dovrebbero avviare PHOTO-CAT solo con:

- `START_WINDOWS.bat`
- `START_UNIX.sh`

## Helper principali

- `start_windows.ps1`, logica principale del launcher Windows.
- `start_linux_macos.sh`, logica principale del launcher macOS/Linux.
- `run_pipeline_windows.bat`, apre la pipeline in una console Windows separata.
- `run_pipeline_unix.sh`, esegue la pipeline da macOS/Linux dopo `Save + run`.
- `fix_console_window.ps1`, regola la dimensione della console Windows.

Gli altri script sono helper manuali o di compatibilità per workflow avanzati. La maggior parte degli utenti non ne ha bisogno.
