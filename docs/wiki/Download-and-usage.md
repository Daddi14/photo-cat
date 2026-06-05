# Download and usage

## Download and get started with PHOTO-CAT

PHOTO-CAT is distributed as a project folder with platform launchers. Normal users should start from the root folder and do not need to open `src/` or `scripts/` manually.

## Get started

1. Download the latest release archive.
2. Extract it to a normal user folder.
3. Run the starter for your operating system:
   - Windows: double-click `START_WINDOWS.bat`
   - macOS/Linux: open Terminal in the folder and run `sh START_UNIX.sh`
4. Wait for PHOTO-CAT to prepare its local environment.
5. Select your catalogue CSV in the graphical configurator.
6. Check the detected column names.
7. Choose the build/query options you need.
8. Click `Save + run`.

## First run

The first run may take a few minutes because PHOTO-CAT prepares a local environment and installs dependencies into `.venv/`.

PHOTO-CAT does not install dependencies into the user’s system Python. If no suitable Python is available, it uses a private runtime under `.runtime/`.

## Windows

Use:

`START_WINDOWS.bat`

The launcher opens a setup console, prepares the local runtime and environment, then opens the graphical configurator.

## macOS/Linux

Use:

`sh START_UNIX.sh`

On macOS, running the launcher from Terminal avoids issues caused by downloaded command files being blocked by Gatekeeper.

## Running the pipeline

After configuring the run, click `Save + run` from the GUI. PHOTO-CAT opens a pipeline console and shows the current stages, progress indicators, and output path.

## Updating PHOTO-CAT

To update an existing installation, replace the project files with the new release files while keeping your own data and output folders.

PHOTO-CAT may rebuild `.venv/` on the next startup if the existing environment is stale, broken, or tied to a previous project path.
