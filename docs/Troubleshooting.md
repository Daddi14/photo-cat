# Troubleshooting

## The GUI does not open

The graphical configurator requires Tkinter.

PHOTO-CAT checks for Tkinter before opening the GUI and attempts to handle common macOS/Linux cases. If the check fails, install Tkinter for the Python version being used or allow PHOTO-CAT to use its local runtime fallback.

## `.venv` is broken after moving the folder

PHOTO-CAT detects moved or broken virtual environments and rebuilds `.venv/` automatically.

If needed, close PHOTO-CAT, delete `.venv/`, and run the starter again.

## A Homebrew Python path no longer exists

Homebrew may remove older Python framework paths during updates.

PHOTO-CAT checks whether `.venv/bin/python` can start. If it cannot, the environment is rebuilt before dependency installation continues.

## Dependencies fail to install

Check the console message and `logs/install.log`.

Common causes include:

- no internet connection during first setup
- blocked network access
- unsupported Python version
- incomplete Python installation
- permission issues in the project folder

## Column name errors

Column names are case-sensitive.

Open the catalogue or targets CSV and confirm that the configured column names match the headers exactly.

## Index folder errors

The query stage requires a complete index folder from the build stage.

Run the build stage again if files are missing, the catalogue changed, or the index folder was moved.

## Output path problems

Make sure the configured output directory is writable and not inside a protected system folder.
