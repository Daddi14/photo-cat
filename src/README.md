# Source code

This folder contains the Python source code for PHOTO-CAT.

Normal users do not need to open this folder. They should use the launcher in the project root:

```text
START_WINDOWS.bat
START_MACOS.command
START_LINUX.sh
```

Important entry points:

```text
configure_gui.py                 Graphical configurator for config.yaml.
config_and_run.py                Runs the selected pipeline steps.
build_neighbors_index.py         Builds the neighbor index.
query_contamination_from_index.py Queries contamination from the index.
install.py                       Creates/updates the local virtual environment.
```
