#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""
Graphical configurator and command centre for PHOTO-CAT.

This GUI edits config.yaml for the build/query pipeline and also exposes every
public ``photo-cat`` subcommand (summarize, plot, export, screen, report,
validate, provenance, merge, benchmark, reproduce, doctor, ...) as an intuitive
form. It uses tkinter from the Python standard library. Runtime dependencies are
installed from pyproject.toml into the local .venv.
"""

import csv
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yaml

from .i18n import (
    LANGUAGE_ENVIRONMENT,
    SUPPORTED_LANGUAGES,
    get_language,
    initialize_language,
    set_language,
    tooltip_for,
    tr,
)
from .load_config import CONTAMINATION_MODES, GAUSSIAN_FWHM_TO_SIGMA
from .photometry.catalogs import CATALOGS
from .photometry.conversion import METHOD_AUTO, METHOD_GAIA_EMPIRICAL, SUPPORTED_CONVERSION_METHODS
from .photometry.library import available_output_bands, library_filter_path, user_filters_root
from .photometry.transformations import find_transformation, supported_empirical_bands

# Sentinel shown in the output-band picker to mean "do not convert; use the
# catalogue band directly". Empty output_band in the saved config maps to this.
NO_CONVERSION_LABEL = "(none - catalogue band)"

# Longest facility description kept in the picker, so one entry stays readable.
_SVO_DESCRIPTION_MAX = 70


def conversion_output_band_values() -> list[str]:
    """Return the output bands offered by the picker.

    Two kinds of band are selectable and they do not overlap: those with an
    installed transmission curve, which any SED method can convert into, and those
    with a published Gaia relation, which need no curve at all. Listing both keeps
    a band such as johnson_v reachable even though no filter file ships for it.
    """
    installed = available_output_bands()
    empirical = [band for band in supported_empirical_bands() if band not in installed]
    return [NO_CONVERSION_LABEL, *installed, *empirical, "custom"]


def conversion_method_note(output_band: str, method: str, catalog: str) -> tuple[str, bool]:
    """Return the explanation shown under the method picker, and whether it warns.

    Which relation actually runs depends on the band, the method, and the catalogue
    together, so the pairing is resolved here and stated in words rather than left
    for the user to infer from three separate dropdowns.
    """
    if (output_band in ("", NO_CONVERSION_LABEL)):
        return ("", False)
    if (method not in (METHOD_GAIA_EMPIRICAL, METHOD_AUTO)):
        return ("", False)

    transformation = find_transformation(output_band, catalog)
    supported = ", ".join(supported_empirical_bands())
    if (transformation is None):
        if (method == METHOD_AUTO):
            return (
                f"auto: no published Gaia relation covers '{output_band}', so the blackbody "
                "conversion through its transmission curve is used for every source.",
                False,
            )
        return (
            f"No calibrated Gaia empirical transformation is available for '{output_band}'. "
            f"Relations exist only for: {supported}. Use blackbody or auto instead.",
            True,
        )

    calibrated = (
        f"{transformation.relation} ({transformation.system}), calibrated for "
        f"{transformation.colour_min:g} <= {transformation.colour_name} <= {transformation.colour_max:g}, "
        f"published scatter {transformation.scatter_mag:g} mag. Needs {catalog} G, BP and RP in the index."
    )
    if (method == METHOD_GAIA_EMPIRICAL):
        return (
            f"Applies {calibrated} Sources outside that colour range are reported as "
            "uncalibrated and left unconverted.",
            False,
        )

    has_curve = library_filter_path(output_band) is not None
    fallback = (
        "outside it the blackbody conversion takes over."
        if has_curve
        else (
            "outside it no fallback is possible, because no transmission curve is installed for "
            f"'{output_band}'; add one under {user_filters_root()} to enable the blackbody fallback."
        )
    )
    return (f"auto: applies {calibrated} Within that range the relation is used; {fallback}", not has_curve)


def svo_facility_display(facility) -> str:
    """Return the picker label for one SVO facility: its name plus site description.

    The description (from SVO itself) is what tells a mission apart from a catalogue
    grouping, so a user does not mistake, say, ``Misc`` for a mission.
    """
    description = (facility.description or "").strip()
    if (len(description) > _SVO_DESCRIPTION_MAX):
        description = description[: _SVO_DESCRIPTION_MAX - 1].rstrip() + "…"
    return f"{facility.name}  —  {description}" if description else facility.name


# How long console output is batched before being written to the widget. Long
# enough to collapse a burst of progress lines into one redraw, short enough to
# still read as live output.
OUTPUT_FLUSH_INTERVAL_MS = 60

# Console scrollback limit. Generous enough to keep a full run's meaningful output,
# bounded so a Tk Text widget cannot grow until it slows the whole window down.
OUTPUT_MAX_LINES = 5000

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_DIR = SRC_DIR.parent
FROZEN = bool(getattr(sys, "frozen", False))
if (FROZEN):
    # In a PyInstaller build the source tree does not exist: anchor user-facing
    # files (config, outputs) next to the executable and read bundled assets
    # from the PyInstaller extraction directory.
    PROJECT_DIR = Path(sys.executable).resolve().parent
    ASSETS_DIR = Path(getattr(sys, "_MEIPASS", str(PROJECT_DIR))) / "assets"
else:
    ASSETS_DIR = PROJECT_DIR / "assets"
CONFIG_PATH = Path(os.environ.get("PHOTO_CAT_CONFIG", str(PROJECT_DIR / "config.yaml"))).resolve()
initialize_language(CONFIG_PATH)
PROJECT_DISPLAY_NAME = "PHOTO-CAT - Photometric Contamination Analyzer Tool"
PROJECT_SHORT_NAME = "PHOTO-CAT"


DEFAULT_CONFIG = {
    "interface": {
        "language": "en",
    },
    "build_neighbors_index": {
        "io": {
            "input_catalog": "data/example_catalog.csv",
            "out_dir": "data/output",
            "usecolumns": [
                "source_id",
                "ra",
                "dec",
                "phot_g_mean_mag",
            ],
            "columns": {
                "source_id": "source_id",
                "ra": "ra",
                "dec": "dec",
                "phot_g_mean_mag": "phot_g_mean_mag",
            },
            "magnitude_columns": {
                "gaia_g": "phot_g_mean_mag",
            },
        },
        "settings": {
            "use_dask": True,
            "calculate_separations": False,
            "max_radius_arcsec": 120.0,
            "chunk_size": 10000,
            "buffer_flush_interval": 200,
        },
    },
    "query_contamination_from_index": {
        "io": {
            "INDEX_DIR": "data/output",
            "TARGETS_INPUT": "data/example_catalog.csv",
            "targets": [],
            "target_source_id_column": "source_id",
        },
        "settings": {
            "field_of_view_arcsec": 47.0,
            "delta_mag": 5,
            "include_missing_targets": False,
            "contamination_bands": ["gaia_g"],
            "photometric_conversion": None,
            "contamination_model": {
                "mode": "top_hat",
                "gaussian_fwhm_arcsec": None,
                "influence_sigma": None,
            },
        },
    },
    "execution": {
        "run_build": True,
        "run_query": True,
        "replace_running_pipeline": True,
    },
}


def suggested_result_output(
    result_json: str | Path,
    role: str,
    selections: dict[str, str] | None = None,
    *,
    avoid_existing: bool = True,
) -> str:
    """Return a descriptive, type-aware output beside one result JSON."""
    result_path = Path(result_json).expanduser()
    selections = selections or {}
    selected_format = selections.get("Format", "").strip().lower()
    selected_kind = selections.get("Kind", "contaminant-counts").strip() or "contaminant-counts"
    backend = selections.get("Backend", "svg").strip().lower()
    extension_by_format = {
        "text": "txt",
        "json": "json",
        "csv": "csv",
        "markdown": "md",
        "html": "html",
        "parquet": "parquet",
        "png": "png",
        "pdf": "pdf",
        "svg": "svg",
    }
    if (role == "summary"):
        suffix, extension = "summary", extension_by_format.get(selected_format, "txt")
    elif (role == "screening"):
        suffix, extension = "screening", extension_by_format.get(selected_format, "csv")
    elif (role == "plot"):
        suffix = selected_kind
        extension = selected_format if selected_format in {"svg", "png", "pdf"} else ("svg" if backend == "svg" else "png")
    elif (role == "publication_plots"):
        suffix, extension = "publication_plots", ""
    elif (role == "report"):
        suffix, extension = "report", extension_by_format.get(selected_format, "html")
    elif (role == "export"):
        suffix, extension = "export", extension_by_format.get(selected_format, "csv")
    elif (role == "validation_stats"):
        suffix, extension = "validation", "json"
    elif (role == "validation_residuals"):
        suffix, extension = "validation_residuals", "csv"
    else:
        raise ValueError(f"Unknown result output role: {role}")

    filename = f"{result_path.stem}_{suffix}"
    candidate = result_path.with_name(filename if extension == "" else f"{filename}.{extension}")
    if (not avoid_existing or not candidate.exists()):
        return str(candidate)
    for index in range(2, 10_000):
        numbered = result_path.with_name(
            f"{filename}_{index}" if extension == "" else f"{filename}_{index}.{extension}"
        )
        if (not numbered.exists()):
            return str(numbered)
    raise RuntimeError("Could not find an available automatic output name.")


def tool_progress_text(frame: int, label: str, elapsed_seconds: float, status: str = "working") -> str:
    """Render one compact GUI-console activity bar without a fabricated percentage."""
    width = 20
    if (status == "working"):
        segment_width = 4
        travel = width - segment_width
        cycle = travel * 2
        offset = max(0, int(frame)) % cycle
        position = offset if offset <= travel else cycle - offset
        bar = "-" * position + "=" * segment_width + "-" * (width - position - segment_width)
    else:
        bar = "=" * width if status == "completed" else "!" * width
    elapsed = max(0, int(elapsed_seconds))
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)
    elapsed_text = f"{hours:d}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes:02d}:{seconds:02d}"
    return f"[{bar}] {tr(status)} {elapsed_text} -- {label}"


def _localize_messageboxes() -> None:
    """Translate every dialog title and message, including existing call sites."""
    for name in ("showerror", "showwarning", "showinfo", "askyesno", "askokcancel"):
        original_name = f"_photocat_original_{name}"
        if (not hasattr(messagebox, original_name)):
            setattr(messagebox, original_name, getattr(messagebox, name))
        original = getattr(messagebox, original_name)

        def localized(title, message=None, *args, _original=original, **kwargs):
            return _original(tr(title), tr(message) if message is not None else message, *args, **kwargs)

        setattr(messagebox, name, localized)


_localize_messageboxes()


class ToolTip:
    """Accessible delayed tooltip shared by all GUI controls and sections."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.window = None
        self.after_id = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, event=None) -> None:
        self.cancel()
        self.after_id = self.widget.after(450, self.show)

    def cancel(self) -> None:
        if (self.after_id is not None):
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def show(self) -> None:
        if (self.window is not None or not self.text):
            return
        try:
            x = self.widget.winfo_rootx() + 18
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.window,
            text=self.text,
            justify="left",
            wraplength=420,
            padx=9,
            pady=7,
            background="#fff8d6",
            foreground="#111827",
            relief="solid",
            borderwidth=1,
        )
        label.pack()

    def hide(self, event=None) -> None:
        self.cancel()
        if (self.window is not None):
            self.window.destroy()
            self.window = None


PLOT_KINDS = [
    "contaminant-counts",
    "flux",
    "separations",
    "flux-vs-separation",
    "contamination-vs-magnitude",
    "sky-map",
]


HELP_TEXT = """Basic pipeline usage:

1. Select your catalog CSV.
2. The GUI automatically sets:
   - Targets CSV to the same file.
   - Output/index folder to an output folder next to the catalog.
   - Query index folder to the same output/index folder.
3. Click Save and run.

Default Gaia-like column names:
Catalog CSV: source_id, ra, dec, phot_g_mean_mag
Targets CSV: source_id

If your catalog uses different names, change the column fields in the GUI to match your CSV header exactly.
Column names are case-sensitive: ra is different from RA, and phot_g_mean_mag is different from PHOT_G_MEAN_MAG.

Targets:
- Easiest mode: leave Targets CSV equal to the catalog CSV.
- CSV mode: select a different CSV containing the configured target source_id column.
- Manual mode: empty the Targets CSV field and write source_ids in the manual list.

Result and catalogue tools (left sidebar, "Results", "Catalogue", "Benchmark", "Diagnostics"):
Each panel maps directly to a photo-cat subcommand. Fill the fields and click Run.
The command output is streamed into the "Tool output" console at the bottom.

Tip for beginners:
Use the default example files first. They are already configured and should run immediately.
"""

HELP_TEXT_IT = """Uso di base della pipeline:

1. Seleziona il CSV del catalogo.
2. La GUI imposta automaticamente:
   - il CSV dei target uguale al catalogo;
   - la cartella output/indice accanto al catalogo;
   - la stessa cartella come indice della query.
3. Premi Salva e avvia la pipeline.

Colonne predefinite in stile Gaia:
CSV catalogo: source_id, ra, dec, phot_g_mean_mag
CSV target: source_id

Se il catalogo usa nomi diversi, modifica i campi delle colonne affinché
corrispondano esattamente alle intestazioni CSV. Maiuscole e minuscole sono
distinte: ra è diverso da RA.

Target:
- modalità semplice: lascia il CSV dei target uguale al catalogo;
- modalità CSV: scegli un file diverso contenente la colonna source_id;
- modalità manuale: svuota il campo CSV target e inserisci gli ID nell'elenco.

Gli strumenti nelle sezioni Risultati, Catalogo, Benchmark e Diagnostica
corrispondono ai comandi photo-cat. Compila i campi e premi Esegui. L'output
appare nella console in basso.

Suggerimento per chi inizia:
usa prima i file di esempio predefiniti. Sono già configurati e dovrebbero
funzionare immediatamente. Passa il mouse su qualsiasi controllo per una
spiegazione del suo significato.
"""


class ConfigGui(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"{PROJECT_DISPLAY_NAME} - {tr('Configurator')}")
        self.resizable(True, True)
        self.minsize(1040, 660)
        self.dark_mode = self.detect_dark_mode()
        self.colors = self.get_theme_colors()
        self.configure(bg=self.colors["window_bg"])
        self.create_styles()
        self.config_data = self.load_config()

        # Pipeline variables.
        self.input_catalog_var = tk.StringVar()
        self.catalog_source_id_column_var = tk.StringVar()
        self.catalog_ra_column_var = tk.StringVar()
        self.catalog_dec_column_var = tk.StringVar()
        self.catalog_mag_column_var = tk.StringVar()
        self.targets_input_var = tk.StringVar()
        self.targets_source_id_column_var = tk.StringVar()
        self.out_dir_var = tk.StringVar()
        self.index_dir_var = tk.StringVar()
        self.max_radius_var = tk.StringVar()
        self.field_of_view_var = tk.StringVar()
        self.delta_mag_var = tk.StringVar()
        self.contamination_bands_var = tk.StringVar()
        self.contamination_mode_var = tk.StringVar(value="top_hat")
        self.gaussian_fwhm_var = tk.StringVar()
        self.influence_sigma_var = tk.StringVar()
        self.conversion_output_band_var = tk.StringVar(value=NO_CONVERSION_LABEL)
        self.conversion_method_var = tk.StringVar(value="blackbody")
        self.conversion_filter_file_var = tk.StringVar()
        self.conversion_catalog_var = tk.StringVar(value="gaia_dr3")
        self.svo_facility_var = tk.StringVar()
        self.svo_filter_var = tk.StringVar()
        self._svo_filters_by_label: dict[str, str] = {}
        self._svo_facility_by_display: dict[str, str] = {}
        self.include_missing_targets_var = tk.BooleanVar()
        self.chunk_size_var = tk.StringVar()
        self.buffer_flush_var = tk.StringVar()
        self.use_dask_var = tk.BooleanVar()
        self.advanced_settings_var = tk.BooleanVar(value=False)
        self.advanced_entry_widgets = []
        self.calculate_separations_var = tk.BooleanVar()
        self.run_build_var = tk.BooleanVar()
        self.run_query_var = tk.BooleanVar()
        self.replace_running_pipeline_var = tk.BooleanVar(value=True)
        self.language_var = tk.StringVar(value=SUPPORTED_LANGUAGES[get_language()])

        self.pipeline_processes = []
        self.pipeline_sessions = []
        self.targets_text = None
        self.magnitude_columns_text = None
        self.catalog_entry = None
        self._applying_catalog_defaults = False
        self._catalog_auto_update_after_id = None

        # Navigation / theming registries.
        self.section_buttons = {}
        self.section_frames = {}
        self.current_section = None
        self._canvases = []
        self._text_widgets = []
        self._result_json_fields = []
        self._recolor_hooks = []
        self.logo_label = None
        self.logo_images = {}
        self.theme_button = None
        self.output_text = None
        self.pending_output: list[str] = []
        self.output_flush_id = None
        self.model_dependent_entries = {}
        self._tooltips: list[ToolTip] = []
        self._tool_progress_counter = 0
        self._tool_progress: dict[int, dict] = {}

        self.create_widgets()
        self.load_values_into_fields()
        self.install_catalog_path_auto_update()
        self.set_advanced_widgets_state()
        self.update_model_field_state()
        self.localize_widget_tree(self)
        self.install_tooltips(self)
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.center_window()

    # ------------------------------------------------------------------
    # Configuration loading
    # ------------------------------------------------------------------
    def load_config(self) -> dict:
        if (not CONFIG_PATH.is_file()):
            return DEFAULT_CONFIG.copy()

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded_config = (yaml.safe_load(f) or {})
        except Exception as exc:
            messagebox.showerror(
                "Config error",
                f"Could not read config.yaml.\n\n{exc}\n\nThe GUI will load default values."
            )
            return DEFAULT_CONFIG.copy()

        return self.merge_defaults(DEFAULT_CONFIG, loaded_config)

    def merge_defaults(self, defaults: dict, loaded: dict) -> dict:
        result = defaults.copy()

        for key, value in loaded.items():
            if (isinstance(value, dict) and isinstance(result.get(key), dict)):
                result[key] = self.merge_defaults(result[key], value)
            else:
                result[key] = value

        return result

    # ------------------------------------------------------------------
    # Theming
    # ------------------------------------------------------------------
    def detect_dark_mode(self) -> bool:
        if (os.name == "nt"):
            try:
                import winreg

                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                ) as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    return (int(value) == 0)
            except Exception:
                return False

        if (sys.platform == "darwin"):
            try:
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return ("dark" in result.stdout.lower())
            except Exception:
                return False

        gtk_theme = os.environ.get("GTK_THEME", "").lower()
        if ("dark" in gtk_theme):
            return True

        return False

    def get_theme_colors(self) -> dict:
        if (self.dark_mode):
            return {
                "window_bg": "#1f2023",
                "panel_bg": "#25272b",
                "sidebar_bg": "#191a1d",
                "entry_bg": "#17181b",
                "console_bg": "#101114",
                "console_fg": "#e6e6e6",
                "text": "#f2f2f2",
                "muted": "#c2c6cf",
                "warning": "#ffd166",
                "border": "#4c505a",
                "tab_bg": "#333741",
                "tab_active": "#465166",
                "accent": "#2f7df6",
                "accent_active": "#1f6ee8",
                "button_bg": "#343842",
                "button_active": "#424856",
            }

        return {
            "window_bg": "#f3f4f6",
            "panel_bg": "#ffffff",
            "sidebar_bg": "#e9ebef",
            "entry_bg": "#ffffff",
            "console_bg": "#f6f7f9",
            "console_fg": "#111827",
            "text": "#111827",
            "muted": "#4b5563",
            "warning": "#9a5400",
            "border": "#c7ccd6",
            "tab_bg": "#e5e7eb",
            "tab_active": "#dbeafe",
            "accent": "#2563eb",
            "accent_active": "#1d4ed8",
            "button_bg": "#eef2f7",
            "button_active": "#dbeafe",
        }

    def create_styles(self) -> None:
        colors = self.colors
        self.style = ttk.Style(self)

        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self.style.configure(
            ".",
            background=colors["window_bg"],
            foreground=colors["text"],
            fieldbackground=colors["entry_bg"],
            font=("Segoe UI", 10),
        )
        self.style.configure("TFrame", background=colors["window_bg"])
        self.style.configure("Sidebar.TFrame", background=colors["sidebar_bg"])
        self.style.configure("Header.TFrame", background=colors["window_bg"])
        self.style.configure("TLabelframe", background=colors["window_bg"], foreground=colors["text"], bordercolor=colors["border"])
        self.style.configure("TLabelframe.Label", background=colors["window_bg"], foreground=colors["text"], font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background=colors["window_bg"], foreground=colors["text"])
        self.style.configure("Muted.TLabel", background=colors["window_bg"], foreground=colors["muted"])
        self.style.configure("Warning.TLabel", background=colors["window_bg"], foreground=colors["warning"])
        self.style.configure("Title.TLabel", background=colors["window_bg"], foreground=colors["text"], font=("Segoe UI", 15, "bold"))
        self.style.configure("Subtitle.TLabel", background=colors["window_bg"], foreground=colors["muted"], font=("Segoe UI", 10))
        self.style.configure("SidebarHeader.TLabel", background=colors["sidebar_bg"], foreground=colors["muted"], font=("Segoe UI", 8, "bold"))
        self.style.configure("PanelTitle.TLabel", background=colors["window_bg"], foreground=colors["text"], font=("Segoe UI", 13, "bold"))
        self.style.configure(
            "TEntry",
            fieldbackground=colors["entry_bg"],
            foreground=colors["text"],
            insertcolor=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
        )
        self.style.map(
            "TEntry",
            fieldbackground=[("disabled", colors["panel_bg"]), ("readonly", colors["entry_bg"]), ("!disabled", colors["entry_bg"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["text"])],
        )
        self.style.configure(
            "TCombobox",
            fieldbackground=colors["entry_bg"],
            background=colors["button_bg"],
            foreground=colors["text"],
            arrowcolor=colors["text"],
            bordercolor=colors["border"],
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", colors["entry_bg"]), ("disabled", colors["panel_bg"])],
            foreground=[("disabled", colors["muted"]), ("!disabled", colors["text"])],
        )
        self.style.configure("TCheckbutton", background=colors["window_bg"], foreground=colors["text"])
        self.style.map(
            "TCheckbutton",
            background=[("active", colors["window_bg"]), ("!active", colors["window_bg"])],
            foreground=[("active", colors["text"]), ("!active", colors["text"])],
        )
        self.style.configure(
            "TButton",
            background=colors["button_bg"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            focusthickness=1,
            focuscolor=colors["accent"],
            padding=(10, 5),
        )
        self.style.map(
            "TButton",
            background=[("active", colors["button_active"]), ("pressed", colors["accent_active"])],
            foreground=[("active", colors["text"]), ("pressed", "#ffffff")],
        )
        self.style.configure(
            "Accent.TButton",
            background=colors["accent"],
            foreground="#ffffff",
            bordercolor=colors["accent_active"],
            padding=(12, 5),
            font=("Segoe UI", 10, "bold"),
        )
        self.style.map(
            "Accent.TButton",
            background=[("active", colors["accent_active"]), ("pressed", colors["accent_active"])],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
        )
        self.style.configure(
            "Section.TButton",
            background=colors["sidebar_bg"],
            foreground=colors["muted"],
            bordercolor=colors["sidebar_bg"],
            anchor="w",
            padding=(12, 6),
            font=("Segoe UI", 10),
        )
        self.style.map(
            "Section.TButton",
            background=[("active", colors["button_active"]), ("pressed", colors["button_active"])],
            foreground=[("active", colors["text"]), ("pressed", colors["text"])],
        )
        self.style.configure(
            "SectionActive.TButton",
            background=colors["accent"],
            foreground="#ffffff",
            bordercolor=colors["accent_active"],
            anchor="w",
            padding=(12, 6),
            font=("Segoe UI", 10, "bold"),
        )
        self.style.map(
            "SectionActive.TButton",
            background=[("active", colors["accent_active"]), ("pressed", colors["accent_active"])],
            foreground=[("active", "#ffffff"), ("pressed", "#ffffff")],
        )
        for orient in ("Vertical", "Horizontal"):
            self.style.configure(
                f"{orient}.TScrollbar",
                background=colors["button_bg"],
                troughcolor=colors["window_bg"],
                bordercolor=colors["border"],
                arrowcolor=colors["muted"],
                darkcolor=colors["button_bg"],
                lightcolor=colors["button_bg"],
                relief="flat",
                gripcount=0,
            )
            self.style.map(
                f"{orient}.TScrollbar",
                background=[("active", colors["button_active"]), ("pressed", colors["accent"])],
                arrowcolor=[("disabled", colors["border"]), ("!disabled", colors["muted"])],
            )

    def load_logo_image(self, dark: bool) -> tk.PhotoImage | None:
        # White logo on a dark background, black logo on a light background.
        name = "photo-cat-logo-dark.png" if dark else "photo-cat-logo-light.png"
        path = ASSETS_DIR / name
        if (not path.is_file()):
            return None

        try:
            image = tk.PhotoImage(file=str(path))
        except Exception:
            return None

        target_height = 54
        height = max(1, image.height())
        factor = max(1, round(height / target_height))
        if (factor > 1):
            try:
                image = image.subsample(factor, factor)
            except Exception:
                pass

        return image

    def set_theme(self, dark: bool) -> None:
        self.dark_mode = dark
        self.colors = self.get_theme_colors()
        self.create_styles()
        self.configure(bg=self.colors["window_bg"])

        for canvas in self._canvases:
            try:
                canvas.configure(background=self.colors[getattr(canvas, "_photocat_bg_key", "window_bg")])
            except Exception:
                pass

        for text_widget in self._text_widgets:
            self.apply_text_colors(text_widget)

        for hook in self._recolor_hooks:
            try:
                hook()
            except Exception:
                pass

        self.update_logo_image()
        if (self.theme_button is not None):
            self.theme_button.configure(text=tr(self.theme_button_label()))

        if (self.current_section is not None):
            self.show_section(self.current_section)

    def toggle_theme(self) -> None:
        self.set_theme(not self.dark_mode)

    def theme_button_label(self) -> str:
        return "Switch to light mode" if self.dark_mode else "Switch to dark mode"

    def localize_widget_tree(self, widget) -> None:
        """Translate every existing widget while retaining its English source key."""
        try:
            current_text = widget.cget("text")
        except (tk.TclError, AttributeError):
            current_text = None
        if (current_text not in (None, "")):
            source_text = getattr(widget, "_photocat_source_text", None)
            if (source_text is None):
                source_text = str(current_text)
                widget._photocat_source_text = source_text
            try:
                widget.configure(text=tr(source_text))
            except tk.TclError:
                pass
        for child in widget.winfo_children():
            self.localize_widget_tree(child)

    def install_tooltips(self, widget) -> None:
        """Attach guidance to every visible label, section, and interactive control."""
        for child in widget.winfo_children():
            class_name = child.winfo_class().lower()
            key = getattr(child, "_photocat_tooltip_key", None)
            if (key is None):
                key = getattr(child, "_photocat_source_text", None)
            if (key is not None or class_name in {"tentry", "text", "tcombobox", "tcheckbutton", "tbutton", "tlabelframe"}):
                if (key is None):
                    key = "Control"
                if ("button" in class_name):
                    kind = "button"
                elif ("labelframe" in class_name or class_name == "tlabel"):
                    kind = "section"
                else:
                    kind = "control"
                tooltip = ToolTip(child, tooltip_for(str(key), kind))
                tooltip.source_key = str(key)
                tooltip.widget_kind = kind
                self._tooltips.append(tooltip)
            self.install_tooltips(child)

    def change_language(self, event=None) -> None:
        """Apply the chosen language immediately and persist it on the next save."""
        selected_name = self.language_var.get()
        language = next((code for code, name in SUPPORTED_LANGUAGES.items() if name == selected_name), "en")
        set_language(language)
        self.config_data.setdefault("interface", {})["language"] = language
        self.title(f"{PROJECT_DISPLAY_NAME} - {tr('Configurator')}")
        self.localize_widget_tree(self)
        for tooltip in self._tooltips:
            tooltip.text = tooltip_for(tooltip.source_key, tooltip.widget_kind)
        if (self.theme_button is not None):
            self.theme_button.configure(text=tr(self.theme_button_label()))

    def apply_text_colors(self, text_widget: tk.Text) -> None:
        is_console = getattr(text_widget, "_photocat_console", False)
        background = self.colors["console_bg"] if is_console else self.colors["entry_bg"]
        foreground = self.colors["console_fg"] if is_console else self.colors["text"]
        try:
            text_widget.configure(
                bg=background,
                fg=foreground,
                insertbackground=foreground,
                selectbackground=self.colors["accent"],
                selectforeground="#ffffff",
                highlightbackground=self.colors["border"],
            )
        except Exception:
            pass

    def update_logo_image(self) -> None:
        if (self.logo_label is None):
            return

        image = self.load_logo_image(self.dark_mode)
        if (image is None):
            self.logo_label.configure(image="", text=PROJECT_SHORT_NAME, style="Title.TLabel")
            self.logo_images["current"] = None
            return

        self.logo_images["current"] = image
        self.logo_label.configure(image=image, text="")

    # ------------------------------------------------------------------
    # Scrollable panels + navigation
    # ------------------------------------------------------------------
    def create_scrollable_frame(
        self,
        parent,
        background_key: str = "window_bg",
        padding: int = 12,
        frame_style: str = "TFrame",
    ) -> tuple[ttk.Frame, ttk.Frame]:
        outer = ttk.Frame(parent)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            outer,
            borderwidth=0,
            highlightthickness=0,
            background=self.colors[background_key],
        )
        canvas._photocat_bg_key = background_key
        self._canvases.append(canvas)
        content = ttk.Frame(canvas, padding=padding, style=frame_style)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        # Coalesce the two expensive resize reactions with after_idle so a burst of
        # Configure events (dragging/maximizing) collapses into a single reflow once
        # the geometry settles, instead of reflowing on every intermediate pixel.
        state = {"scroll_id": None, "width_id": None, "applied_width": -1, "target_width": -1}

        def content_fits() -> bool:
            """Return whether the whole content is already visible in the canvas."""
            first, last = canvas.yview()
            return (last - first) >= 1.0

        def apply_scroll_region():
            state["scroll_id"] = None
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
                # Enlarging the window can leave the view scrolled past content that
                # now fits, which strands the panel showing blank space below it.
                if (content_fits()):
                    canvas.yview_moveto(0.0)
            except tk.TclError:
                pass

        def update_scroll_region(event=None):
            if (state["scroll_id"] is None):
                state["scroll_id"] = canvas.after_idle(apply_scroll_region)

        def apply_content_width():
            state["width_id"] = None
            width = state["target_width"]
            if (width != state["applied_width"]):
                state["applied_width"] = width
                try:
                    canvas.itemconfigure(window_id, width=width)
                except tk.TclError:
                    pass

        def resize_content(event):
            # Reflowing the embedded window (wrapped labels, grid geometry) is the costly
            # step, so defer it to idle and only when the width truly changed.
            state["target_width"] = event.width
            if (state["width_id"] is None):
                state["width_id"] = canvas.after_idle(apply_content_width)
            # Growing the canvas changes how much of the content fits, so the scroll
            # region has to be recomputed here as well. Reacting only to content
            # Configure events left a stale, too-tall region after the window was
            # enlarged, which is what kept a full scrollbar scrollable.
            update_scroll_region()

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(outer, orient="vertical", style="Vertical.TScrollbar", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Every wheel handler goes through this guard: when the content already fits,
        # there is nothing to scroll, and scrolling anyway drags the panel away from
        # its content. The guard reads the live view rather than trusting the scroll
        # region, so it stays correct even if the region is momentarily stale.
        def scroll_units(units: int) -> None:
            if (content_fits()):
                return
            canvas.yview_scroll(units, "units")

        def on_mousewheel(event):
            if (event.delta != 0):
                scroll_units(int(-1 * (event.delta / 120)))

        def on_linux_scroll_up(event):
            scroll_units(-3)

        def on_linux_scroll_down(event):
            scroll_units(3)

        def bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", on_mousewheel)
            canvas.bind_all("<Button-4>", on_linux_scroll_up)
            canvas.bind_all("<Button-5>", on_linux_scroll_down)

        def unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", bind_mousewheel)
        canvas.bind("<Leave>", unbind_mousewheel)

        return outer, content

    def add_sidebar_header(self, parent, text: str, row: int) -> None:
        label = ttk.Label(parent, text=text, style="SidebarHeader.TLabel")
        label._photocat_tooltip_key = text
        label.grid(row=row, column=0, sticky="w", padx=12, pady=(12, 2))

    def add_section(self, key: str, label: str, parent: ttk.Frame, sidebar: ttk.Frame, row: int) -> ttk.Frame:
        button = ttk.Button(
            sidebar,
            text=label,
            style="Section.TButton",
            command=lambda section_key=key: self.show_section(section_key),
        )
        button.grid(row=row, column=0, sticky="ew", padx=6, pady=1)
        self.section_buttons[key] = button

        outer, content = self.create_scrollable_frame(parent)
        outer.grid(row=0, column=0, sticky="nsew")
        # Start hidden: only the active section stays mapped, so inactive panels do
        # not receive resize/Configure events and cannot reflow while the window is
        # dragged or maximized. This is the main fix for resize/fullscreen lag.
        outer.grid_remove()
        content.columnconfigure(1, weight=1)
        self.section_frames[key] = outer
        return content

    def show_section(self, key: str) -> None:
        frame = self.section_frames.get(key)
        if (frame is None):
            return

        if (self.current_section is not None and self.current_section != key):
            previous = self.section_frames.get(self.current_section)
            if (previous is not None):
                previous.grid_remove()

        frame.grid()
        self.current_section = key
        # Keep tool 'Result JSON' fields pointed at the latest generated result.
        self.refresh_result_json_fields()

        for section_key, button in self.section_buttons.items():
            style = "SectionActive.TButton" if (section_key == key) else "Section.TButton"
            button.configure(style=style)

    # ------------------------------------------------------------------
    # Top-level layout
    # ------------------------------------------------------------------
    def create_widgets(self) -> None:
        self.geometry("1180x840")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=3)
        root.rowconfigure(2, weight=1)

        self.build_header(root)

        body = ttk.Frame(root)
        body.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        sidebar_outer, sidebar = self.create_scrollable_frame(
            body, background_key="sidebar_bg", padding=0, frame_style="Sidebar.TFrame"
        )
        sidebar_outer.configure(width=208)
        sidebar_outer.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        sidebar_outer.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)

        section_body = ttk.Frame(body)
        section_body.grid(row=0, column=1, sticky="nsew")
        section_body.columnconfigure(0, weight=1)
        section_body.rowconfigure(0, weight=1)

        self.build_sidebar_and_sections(sidebar, section_body)
        self.build_output_console(root)
        self.build_action_bar(root)

        self.show_section("files")

    def build_header(self, root) -> None:
        header = ttk.Frame(root, style="Header.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        self.logo_label = ttk.Label(header, style="Title.TLabel")
        self.logo_label.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 14))
        self.update_logo_image()

        title = ttk.Label(header, text=PROJECT_SHORT_NAME, style="Title.TLabel")
        title.grid(row=0, column=1, sticky="sw")

        subtitle = ttk.Label(
            header,
            text="Photometric Contamination Analyzer Tool - configure the pipeline and run every command.",
            style="Subtitle.TLabel",
        )
        subtitle.grid(row=1, column=1, sticky="nw")

        language_label = ttk.Label(header, text="Language", style="Subtitle.TLabel")
        language_label.grid(row=0, column=2, sticky="e", padx=(8, 5))
        language_label._photocat_tooltip_key = "Language"
        language_combo = ttk.Combobox(
            header,
            textvariable=self.language_var,
            values=list(SUPPORTED_LANGUAGES.values()),
            state="readonly",
            width=10,
        )
        language_combo.grid(row=0, column=3, sticky="e", padx=(0, 8))
        language_combo._photocat_tooltip_key = "Language"
        language_combo.bind("<<ComboboxSelected>>", self.change_language)

        self.theme_button = ttk.Button(header, text=self.theme_button_label(), command=self.toggle_theme)
        self.theme_button.grid(row=0, column=4, rowspan=2, sticky="e")

    def build_sidebar_and_sections(self, sidebar, section_body) -> None:
        row = 0
        self.add_sidebar_header(sidebar, "Configure pipeline", row)
        row += 1
        for key, label, builder in (
            ("files", "Files & columns", self.build_files_panel),
            ("settings", "Search settings", self.build_settings_panel),
            ("options", "Run options", self.build_options_panel),
        ):
            content = self.add_section(key, label, section_body, sidebar, row)
            content.columnconfigure(1, weight=1)
            builder(content)
            row += 1

        self.add_sidebar_header(sidebar, "Results", row)
        row += 1
        for key, label, spec_builder in (
            ("summarize", "Summarize", self.spec_summarize),
            ("screen", "Screen / rank", self.spec_screen),
            ("plot", "Plot", self.spec_plot),
            ("publication", "Publication plots", self.spec_publication_plots),
            ("report", "Report", self.spec_report),
            ("export", "Export", self.spec_export),
            ("validate", "Validate results", self.spec_validate),
        ):
            content = self.add_section(key, label, section_body, sidebar, row)
            self.build_tool_panel(content, spec_builder())
            row += 1

        self.add_sidebar_header(sidebar, "Catalogue", row)
        row += 1
        for key, label, spec_builder in (
            ("provenance", "Provenance", self.spec_provenance),
            ("merge", "Merge bright stars", self.spec_merge_bright_stars),
        ):
            content = self.add_section(key, label, section_body, sidebar, row)
            self.build_tool_panel(content, spec_builder())
            row += 1

        self.add_sidebar_header(sidebar, "Benchmark", row)
        row += 1
        for key, label, spec_builder in (
            ("benchmark", "Benchmark", self.spec_benchmark),
            ("benchmark-table", "Benchmark table", self.spec_benchmark_table),
            ("reproduce", "Reproduce", self.spec_reproduce),
        ):
            content = self.add_section(key, label, section_body, sidebar, row)
            self.build_tool_panel(content, spec_builder())
            row += 1

        self.add_sidebar_header(sidebar, "Diagnostics", row)
        row += 1
        for key, label, spec_builder in (
            ("doctor", "Doctor", self.spec_doctor),
        ):
            content = self.add_section(key, label, section_body, sidebar, row)
            self.build_tool_panel(content, spec_builder())
            row += 1

    def build_output_console(self, root) -> None:
        console = ttk.LabelFrame(root, text="Tool output", padding=(8, 6))
        console.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        console.columnconfigure(0, weight=1)
        console.rowconfigure(1, weight=1)

        header = ttk.Frame(console)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(
            header,
            text="Output from Results / Catalogue / Benchmark / Diagnostics commands appears here.",
            style="Muted.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="Clear", command=self.clear_output).grid(row=0, column=1, sticky="e")

        self.output_text = tk.Text(console, height=8, wrap="word", relief="solid", borderwidth=1)
        self.output_text._photocat_console = True
        self.output_text._photocat_tooltip_key = "Tool output"
        self.output_text.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        self._text_widgets.append(self.output_text)
        self.apply_text_colors(self.output_text)

        scrollbar = ttk.Scrollbar(console, orient="vertical", style="Vertical.TScrollbar", command=self.output_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns", pady=(6, 0))
        self.output_text.configure(yscrollcommand=scrollbar.set, state="disabled")

    def build_action_bar(self, root) -> None:
        buttons = ttk.Frame(root)
        buttons.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(4, weight=1)

        ttk.Button(buttons, text="Help", command=self.show_help).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Load example config", command=self.load_example_config).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Save config.yaml", command=self.save_config).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(buttons, text="Save and run pipeline", command=self.save_and_run, style="Accent.TButton").grid(row=0, column=3)

    # ------------------------------------------------------------------
    # Pipeline panels
    # ------------------------------------------------------------------
    def build_files_panel(self, files_tab) -> None:
        ttk.Label(files_tab, text="Files and columns", style="PanelTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        self.catalog_entry = self.add_file_row(files_tab, 1, "Catalog CSV", self.input_catalog_var, self.browse_catalog)
        self.catalog_entry.bind("<FocusOut>", self.apply_catalog_defaults_from_event)
        self.catalog_entry.bind("<Return>", self.apply_catalog_defaults_from_event)

        catalog_columns = ttk.LabelFrame(files_tab, text="Catalog column names", padding=8)
        catalog_columns.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        catalog_columns.columnconfigure(1, weight=1)
        catalog_columns.columnconfigure(3, weight=1)

        ttk.Label(
            catalog_columns,
            text=(
                "Default Gaia-like names are pre-filled. Change them only if your CSV headers are different. "
                "The names must match the catalog CSV exactly, including uppercase/lowercase."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        self.add_entry_row(catalog_columns, 1, "Catalog Source ID column", self.catalog_source_id_column_var, column_offset=0)
        self.add_entry_row(catalog_columns, 1, "Catalog RA column", self.catalog_ra_column_var, column_offset=2)
        self.add_entry_row(catalog_columns, 2, "Catalog Dec column", self.catalog_dec_column_var, column_offset=0)
        self.add_entry_row(catalog_columns, 2, "Catalog magnitude column", self.catalog_mag_column_var, column_offset=2)

        magnitude_bands = ttk.LabelFrame(files_tab, text="Magnitude bands (optional extra bands)", padding=8)
        magnitude_bands.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        magnitude_bands.columnconfigure(0, weight=1)

        ttk.Label(
            magnitude_bands,
            text=(
                "One band=catalog_column per line, for example gaia_bp=phot_bp_mean_mag. "
                "gaia_g is always mapped to the catalog magnitude column above. "
                "Extra bands can then be requested in Search settings > Contamination bands."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))

        self.magnitude_columns_text = self.make_text_widget(magnitude_bands, height=3)
        self.magnitude_columns_text._photocat_tooltip_key = "Magnitude bands (optional extra bands)"
        self.magnitude_columns_text.grid(row=1, column=0, sticky="ew")

        self.add_file_row(files_tab, 4, "Targets CSV", self.targets_input_var, self.browse_targets)

        target_columns = ttk.LabelFrame(files_tab, text="Targets column name", padding=8)
        target_columns.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        target_columns.columnconfigure(1, weight=1)

        ttk.Label(
            target_columns,
            text=(
                "Default target column is source_id. Change it only if your targets CSV uses another header. "
                "This is case-sensitive. Manual targets ignore this field."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        self.add_entry_row(target_columns, 1, "Targets Source ID column", self.targets_source_id_column_var)

        self.add_folder_row(files_tab, 6, "Output/index folder", self.out_dir_var, self.browse_out_dir)
        self.add_folder_row(files_tab, 7, "Query index folder", self.index_dir_var, self.browse_index_dir)

        manual_targets = ttk.LabelFrame(files_tab, text="Manual targets", padding=8)
        manual_targets.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        manual_targets.columnconfigure(0, weight=1)

        ttk.Label(
            manual_targets,
            text=(
                "Optional. Leave Targets CSV empty/null to use this source_id list instead. "
                "Use one source_id per line, or separate them with commas."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        self.targets_text = self.make_text_widget(manual_targets, height=3)
        self.targets_text._photocat_tooltip_key = "Manual targets"
        self.targets_text.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Button(manual_targets, text="Use manual list", command=self.use_manual_targets).grid(row=1, column=1, sticky="n")

    def build_settings_panel(self, settings_tab) -> None:
        ttk.Label(settings_tab, text="Search settings", style="PanelTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        self.add_entry_row(settings_tab, 1, "Max build radius, arcsec", self.max_radius_var)
        self.add_entry_row(settings_tab, 2, "Query aperture radius, arcsec", self.field_of_view_var)
        self.add_entry_row(settings_tab, 3, "Delta magnitude", self.delta_mag_var)
        self.add_entry_row(settings_tab, 4, "Contamination bands (comma-separated, or all)", self.contamination_bands_var)

        ttk.Label(
            settings_tab,
            text=(
                "The aperture radius defines the extraction/screening circle and must be equal to or smaller "
                "than the max build radius. With a Gaussian PSF the outer influence radius is not set here: it "
                "is derived below from the PSF width and the number of sigmas you choose to keep."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 8))

        model = ttk.LabelFrame(settings_tab, text="Contamination weighting model", padding=8)
        model.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        model.columnconfigure(1, weight=1)

        ttk.Label(
            model,
            text=(
                "top_hat keeps the historical catalogue/aperture flux estimate. gaussian_psf models a 2D circular "
                "Gaussian PSF, where each source's flux decays with angular distance from the aperture centre. "
                "It needs the PSF FWHM and the number of sigmas of leakage to keep."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(model, text="Model mode").grid(row=1, column=0, sticky="w", pady=4)
        mode_combo = ttk.Combobox(
            model,
            textvariable=self.contamination_mode_var,
            values=list(CONTAMINATION_MODES),
            state="readonly",
            width=22,
        )
        mode_combo._photocat_tooltip_key = "Contamination weighting model"
        mode_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
        mode_combo.bind("<<ComboboxSelected>>", lambda event: self.update_model_field_state())

        fwhm_entry = self.add_entry_row(model, 2, "Gaussian FWHM, arcsec", self.gaussian_fwhm_var)
        sigma_entry = self.add_entry_row(model, 3, "Influence radius, number of sigmas", self.influence_sigma_var)
        self.model_dependent_entries = {"gaussian_fwhm": fwhm_entry, "influence_sigma": sigma_entry}

        # Live readout so the user can see the arcsec radius their sigma choice implies.
        self.derived_influence_label = ttk.Label(model, text="", style="Muted.TLabel", wraplength=880, justify="left")
        self.derived_influence_label.grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        for variable in (self.gaussian_fwhm_var, self.influence_sigma_var):
            variable.trace_add("write", lambda *_: self.update_derived_influence_radius())

        self.build_conversion_panel(settings_tab, row=9)

        advanced = ttk.LabelFrame(settings_tab, text="Advanced performance settings", padding=8)
        advanced.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        advanced.columnconfigure(1, weight=1)

        ttk.Label(
            advanced,
            text=(
                "Leave these locked unless you know what you are doing. Wrong values can make the tool "
                "slower, use too much RAM, write too often to disk, or make long runs harder to resume safely."
            ),
            style="Warning.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Checkbutton(
            advanced,
            text="Enable advanced settings",
            variable=self.advanced_settings_var,
            command=self.toggle_advanced_settings,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 6))

        chunk_size_entry = self.add_entry_row(advanced, 2, "Chunk size", self.chunk_size_var)
        buffer_flush_entry = self.add_entry_row(advanced, 3, "Buffer flush / checkpoint every N chunks", self.buffer_flush_var)
        self.advanced_entry_widgets = [chunk_size_entry, buffer_flush_entry]

    def build_options_panel(self, options_tab) -> None:
        ttk.Label(options_tab, text="Run options", style="PanelTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        checks = ttk.LabelFrame(options_tab, text="Options", padding=8)
        checks.grid(row=1, column=0, columnspan=3, sticky="ew")

        ttk.Checkbutton(checks, text="Use Dask for very large CSV files", variable=self.use_dask_var).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checks, text="Store neighbor separations on disk", variable=self.calculate_separations_var).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checks, text="Run build step", variable=self.run_build_var).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checks, text="Run query step", variable=self.run_query_var).grid(row=3, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checks, text="Include missing target rows in results", variable=self.include_missing_targets_var).grid(row=4, column=0, sticky="w", pady=2)
        ttk.Checkbutton(
            checks,
            text="Replace running pipeline when Save and run is clicked",
            variable=self.replace_running_pipeline_var,
        ).grid(row=5, column=0, sticky="w", pady=(8, 2))

        ttk.Label(
            checks,
            text=(
                "Enabled: the previous pipeline window opened by this GUI is closed before a new run starts. "
                "Disabled: each Save and run opens a separate pipeline window."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=6, column=0, sticky="w", pady=(0, 2))

        help_box = ttk.LabelFrame(options_tab, text="Quick help", padding=8)
        help_box.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        ttk.Label(
            help_box,
            text=(
                "Recommended workflow:\n"
                "1. Select Catalog CSV in Files & columns.\n"
                "2. Check that Targets CSV and output folders were auto-filled correctly.\n"
                "3. Leave the Gaia-like column names unchanged unless your CSV uses different headers.\n"
                "4. Click Save and run pipeline.\n"
                "5. Use the Results and Catalogue panels on the output JSON afterwards."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

    # ------------------------------------------------------------------
    # Row helpers
    # ------------------------------------------------------------------
    def make_text_widget(self, parent, height: int, wrap: str = "none") -> tk.Text:
        text_widget = tk.Text(parent, height=height, wrap=wrap, relief="solid", borderwidth=1)
        self._text_widgets.append(text_widget)
        self.apply_text_colors(text_widget)
        return text_widget

    def add_file_row(self, parent, row: int, label: str, variable: tk.StringVar, command):
        label_widget = ttk.Label(parent, text=label)
        label_widget._photocat_tooltip_key = label
        label_widget.grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=70)
        entry._photocat_tooltip_key = label
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
        button = ttk.Button(parent, text="Browse...", command=command)
        button._photocat_tooltip_key = label
        button.grid(row=row, column=2, pady=4)
        return entry

    def add_folder_row(self, parent, row: int, label: str, variable: tk.StringVar, command) -> None:
        label_widget = ttk.Label(parent, text=label)
        label_widget._photocat_tooltip_key = label
        label_widget.grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=70)
        entry._photocat_tooltip_key = label
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
        button = ttk.Button(parent, text="Browse...", command=command)
        button._photocat_tooltip_key = label
        button.grid(row=row, column=2, pady=4)

    def add_entry_row(self, parent, row: int, label: str, variable: tk.StringVar, column_offset: int = 0):
        label_widget = ttk.Label(parent, text=label)
        label_widget._photocat_tooltip_key = label
        label_widget.grid(row=row, column=column_offset, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=22)
        entry._photocat_tooltip_key = label
        entry.grid(row=row, column=column_offset + 1, sticky="w", padx=(10, 18), pady=4)
        return entry

    # ------------------------------------------------------------------
    # Load config into fields
    # ------------------------------------------------------------------
    def load_values_into_fields(self) -> None:
        build_io = self.config_data["build_neighbors_index"]["io"]
        build_settings = self.config_data["build_neighbors_index"]["settings"]
        query_io = self.config_data["query_contamination_from_index"]["io"]
        query_settings = self.config_data["query_contamination_from_index"]["settings"]
        execution = self.config_data["execution"]
        build_columns = self.get_catalog_columns_from_io(build_io)
        model = query_settings.get("contamination_model") or {}
        conversion = query_settings.get("photometric_conversion") or {}

        self.input_catalog_var.set(str(build_io.get("input_catalog", "")))
        self.catalog_source_id_column_var.set(str(build_columns.get("source_id", "source_id")))
        self.catalog_ra_column_var.set(str(build_columns.get("ra", "ra")))
        self.catalog_dec_column_var.set(str(build_columns.get("dec", "dec")))
        self.catalog_mag_column_var.set(str(build_columns.get("phot_g_mean_mag", "phot_g_mean_mag")))
        self.targets_input_var.set("" if (query_io.get("TARGETS_INPUT") is None) else str(query_io.get("TARGETS_INPUT", "")))
        self.targets_source_id_column_var.set(str(query_io.get("target_source_id_column", "source_id") or "source_id"))
        self.out_dir_var.set(str(build_io.get("out_dir", "data/output")))
        self.index_dir_var.set(str(query_io.get("INDEX_DIR", "data/output")))
        self.max_radius_var.set(str(build_settings.get("max_radius_arcsec", 120.0)))
        self.field_of_view_var.set(str(query_settings.get("field_of_view_arcsec", 47.0)))
        output_band = conversion.get("output_band")
        self.conversion_output_band_var.set(NO_CONVERSION_LABEL if not output_band else str(output_band))
        self.conversion_method_var.set(str(conversion.get("conversion_method") or "blackbody"))
        self.conversion_filter_file_var.set(str(conversion.get("filter_file") or ""))
        self.conversion_catalog_var.set(str(conversion.get("catalog") or "gaia_dr3"))
        self.delta_mag_var.set(str(query_settings.get("delta_mag", 5)))
        self.contamination_bands_var.set(", ".join(query_settings.get("contamination_bands") or ["gaia_g"]))
        self.contamination_mode_var.set(str(model.get("mode") or "top_hat"))
        self.gaussian_fwhm_var.set("" if (model.get("gaussian_fwhm_arcsec") is None) else str(model.get("gaussian_fwhm_arcsec")))
        self.influence_sigma_var.set("" if (model.get("influence_sigma") is None) else str(model.get("influence_sigma")))
        self.include_missing_targets_var.set(bool(query_settings.get("include_missing_targets", False)))
        self.chunk_size_var.set(str(build_settings.get("chunk_size", 10000)))
        self.buffer_flush_var.set(str(build_settings.get("buffer_flush_interval", 200)))
        self.use_dask_var.set(bool(build_settings.get("use_dask", True)))
        self.calculate_separations_var.set(bool(build_settings.get("calculate_separations", False)))
        self.run_build_var.set(bool(execution.get("run_build", True)))
        self.run_query_var.set(bool(execution.get("run_query", True)))
        self.replace_running_pipeline_var.set(bool(execution.get("replace_running_pipeline", True)))
        self.advanced_settings_var.set(False)
        self.set_manual_targets_text(query_io.get("targets", []) or [])
        self.set_magnitude_columns_text(build_io.get("magnitude_columns", {}) or {}, build_columns.get("phot_g_mean_mag", "phot_g_mean_mag"))
        self.set_advanced_widgets_state()
        self.update_model_field_state()

    def get_catalog_columns_from_io(self, build_io: dict) -> dict:
        columns = build_io.get("columns", {}) or {}
        usecolumns = build_io.get("usecolumns", []) or []

        return {
            "source_id": str(columns.get("source_id") or (usecolumns[0] if len(usecolumns) > 0 else "source_id")),
            "ra": str(columns.get("ra") or (usecolumns[1] if len(usecolumns) > 1 else "ra")),
            "dec": str(columns.get("dec") or (usecolumns[2] if len(usecolumns) > 2 else "dec")),
            "phot_g_mean_mag": str(columns.get("phot_g_mean_mag") or (usecolumns[3] if len(usecolumns) > 3 else "phot_g_mean_mag")),
        }

    def set_manual_targets_text(self, targets: list) -> None:
        if (self.targets_text is None):
            return

        self.targets_text.delete("1.0", "end")
        if (targets):
            self.targets_text.insert("1.0", "\n".join(str(target) for target in targets))

    def set_magnitude_columns_text(self, magnitude_columns: dict, mag_column: str) -> None:
        if (self.magnitude_columns_text is None):
            return

        lines = []
        for band, column in magnitude_columns.items():
            # gaia_g is derived from the catalog magnitude column; only surface extra bands.
            if (band == "gaia_g" and str(column) == str(mag_column)):
                continue
            lines.append(f"{band}={column}")

        self.magnitude_columns_text.delete("1.0", "end")
        if (lines):
            self.magnitude_columns_text.insert("1.0", "\n".join(lines))

    def set_advanced_widgets_state(self) -> None:
        state = "normal" if (self.advanced_settings_var.get()) else "disabled"

        for widget in self.advanced_entry_widgets:
            widget.configure(state=state)

    def build_conversion_panel(self, settings_tab, row: int) -> None:
        """Build the optional catalogue-to-output-band photometric conversion group."""
        conversion = ttk.LabelFrame(settings_tab, text="Photometric band conversion (optional)", padding=8)
        conversion.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        conversion.columnconfigure(1, weight=1)

        ttk.Label(
            conversion,
            text=(
                "Choose the catalogue and the output band used for contamination. If that exact band "
                "is stored in the index, PHOTO-CAT uses its nominal catalogue magnitude directly. "
                "Otherwise BP-RP supplies the temperature used to convert each source into the chosen band."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(conversion, text="Catalogue").grid(row=1, column=0, sticky="w", pady=4)
        catalog_combo = ttk.Combobox(
            conversion,
            textvariable=self.conversion_catalog_var,
            values=sorted(CATALOGS),
            state="readonly",
            width=24,
        )
        catalog_combo._photocat_tooltip_key = "Catalogue"
        catalog_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)

        ttk.Label(conversion, text="Output band").grid(row=2, column=0, sticky="w", pady=4)
        output_combo = ttk.Combobox(
            conversion,
            textvariable=self.conversion_output_band_var,
            values=conversion_output_band_values(),
            state="readonly",
            width=24,
        )
        output_combo._photocat_tooltip_key = "Output band"
        output_combo.grid(row=2, column=1, sticky="w", padx=(10, 0), pady=4)
        output_combo.bind("<<ComboboxSelected>>", lambda event: self.update_conversion_field_state())

        ttk.Label(conversion, text="Conversion method").grid(row=3, column=0, sticky="w", pady=4)
        method_combo = ttk.Combobox(
            conversion,
            textvariable=self.conversion_method_var,
            values=list(SUPPORTED_CONVERSION_METHODS),
            state="readonly",
            width=24,
        )
        method_combo._photocat_tooltip_key = "Conversion method"
        method_combo.grid(row=3, column=1, sticky="w", padx=(10, 0), pady=4)

        self.conversion_output_combo = output_combo
        filter_entry = self.add_file_row(
            conversion, 4, "Custom filter file", self.conversion_filter_file_var, self.browse_conversion_filter
        )
        self.conversion_dependent_entries = {"filter_file": filter_entry, "method": method_combo, "catalog": catalog_combo}

        # Says which relation will run for the current band and method, or why none
        # can, so an unsupported pairing is visible before the run rather than after.
        self.conversion_method_note = ttk.Label(
            conversion, text="", style="Muted.TLabel", wraplength=880, justify="left"
        )
        self.conversion_method_note.grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Label(
            conversion,
            text=(
                "A custom filter file is required only for the custom output band. Format: two columns "
                "'wavelength transmission', optional headers '# unit: nm|angstrom|micron' and "
                "'# transmission: fraction|percent'."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 0))

        self.build_svo_download_panel(conversion, row=7)

        self.conversion_output_band_var.trace_add("write", lambda *_: self.update_conversion_field_state())
        self.conversion_method_var.trace_add("write", lambda *_: self.update_conversion_field_state())
        self.conversion_catalog_var.trace_add("write", lambda *_: self.update_conversion_field_state())
        self.update_conversion_field_state()

    def build_svo_download_panel(self, parent, row: int) -> None:
        """Build the SVO Filter Profile Service downloader inside the conversion group."""
        svo = ttk.LabelFrame(parent, text="Download a filter from SVO", padding=8)
        svo.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        svo.columnconfigure(1, weight=1)

        ttk.Label(
            svo,
            text=(
                "Fetch any filter from the SVO Filter Profile Service. Pick a facility, list its filters, "
                "then download one; it is saved to the filter library and selected as the output band."
            ),
            style="Muted.TLabel",
            wraplength=860,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(svo, text="Facility").grid(row=1, column=0, sticky="w", pady=4)
        # Seed with the bundled list so the picker works instantly and offline, then
        # reload it live from SVO in the background so it always mirrors the site
        # rather than a hand-maintained list.
        # Populated live from the SVO index by refresh_svo_facilities(); starts empty
        # and editable so a known facility can be typed before the fetch returns.
        self.svo_facility_combo = ttk.Combobox(
            svo, textvariable=self.svo_facility_var, values=[], width=46, height=20
        )
        self.svo_facility_combo._photocat_tooltip_key = "Facility"
        self.svo_facility_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
        self.refresh_svo_facilities()
        self.svo_list_button = ttk.Button(svo, text="List filters", command=self.list_svo_filters)
        self.svo_list_button._photocat_tooltip_key = "List filters"
        self.svo_list_button.grid(row=1, column=2, sticky="w", padx=(10, 0), pady=4)

        ttk.Label(svo, text="Filter").grid(row=2, column=0, sticky="w", pady=4)
        self.svo_filter_combo = ttk.Combobox(
            svo, textvariable=self.svo_filter_var, values=[], state="readonly", width=48
        )
        self.svo_filter_combo._photocat_tooltip_key = "Filter"
        self.svo_filter_combo.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=4)
        self.svo_download_button = ttk.Button(svo, text="Download and use", command=self.download_svo_filter, state="disabled")
        self.svo_download_button._photocat_tooltip_key = "Download and use"
        self.svo_download_button.grid(row=2, column=2, sticky="w", padx=(10, 0), pady=4)

        self.svo_status_label = ttk.Label(svo, text="", style="Muted.TLabel", wraplength=860, justify="left")
        self.svo_status_label.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def update_conversion_field_state(self) -> None:
        """Enable conversion inputs only when a band conversion is actually selected."""
        entries = getattr(self, "conversion_dependent_entries", None)
        if (not entries):
            return

        band = self.conversion_output_band_var.get().strip()
        converting = band not in ("", NO_CONVERSION_LABEL)
        entries["method"].configure(state="readonly" if converting else "disabled")
        entries["catalog"].configure(state="readonly" if converting else "disabled")
        # The custom filter file only matters for the custom band.
        entries["filter_file"].configure(state="normal" if (band == "custom") else "disabled")

        note = getattr(self, "conversion_method_note", None)
        if (note is not None):
            text, warns = conversion_method_note(
                band,
                self.conversion_method_var.get().strip(),
                self.conversion_catalog_var.get().strip() or "gaia_dr3",
            )
            note.configure(text=tr(text) if text else "", style="Warning.TLabel" if warns else "Muted.TLabel")

    def refresh_svo_facilities(self) -> None:
        """Reload the facility picker from the live SVO index in the background.

        Runs automatically when the panel opens, so the dropdown always mirrors the
        SVO site and a newly added facility appears without shipping a new tool
        version. A network failure silently leaves the bundled list in place.
        """
        def worker():
            from .photometry import svo
            try:
                facilities = svo.list_facilities()
            except Exception:
                return
            if (facilities):
                display_to_name = {svo_facility_display(f): f.name for f in facilities}
                self.after(0, lambda: self._svo_facilities_ready(display_to_name))

        threading.Thread(target=worker, daemon=True).start()

    def _svo_facilities_ready(self, display_to_name: dict) -> None:
        self._svo_facility_by_display = display_to_name
        self.svo_facility_combo.configure(values=list(display_to_name))

    def list_svo_filters(self) -> None:
        """Fetch the filter list for the chosen facility on a background thread."""
        selection = self.svo_facility_var.get().strip()
        # A picked entry is "Name  —  description"; a typed one is the bare name.
        facility = self._svo_facility_by_display.get(selection, selection)
        if (facility == ""):
            self.svo_status_label.configure(text=tr("Choose a facility before listing filters."))
            return
        self.svo_list_button.configure(state="disabled")
        self.svo_status_label.configure(text=tr("Listing filters from SVO..."))

        def worker():
            from .photometry import svo
            try:
                filters = svo.list_filters(facility)
            except svo.SvoError as error:
                self.after(0, self._svo_list_failed, str(error))
                return
            labels_to_ids = {f.label(): f.filter_id for f in filters}
            self.after(0, self._svo_list_ready, list(labels_to_ids), labels_to_ids)

        threading.Thread(target=worker, daemon=True).start()

    def _svo_list_ready(self, labels: list, labels_to_ids: dict) -> None:
        self._svo_filters_by_label = labels_to_ids
        self.svo_filter_combo.configure(values=labels)
        if (labels):
            self.svo_filter_var.set(labels[0])
            self.svo_download_button.configure(state="normal")
        self.svo_list_button.configure(state="normal")
        self.svo_status_label.configure(text=tr("Found {count} filters. Choose one and download it.").format(count=len(labels)))

    def _svo_list_failed(self, message: str) -> None:
        self.svo_list_button.configure(state="normal")
        self.svo_download_button.configure(state="disabled")
        self.svo_filter_combo.configure(values=[])
        self.svo_status_label.configure(text=message)

    def download_svo_filter(self) -> None:
        """Download the selected SVO filter into the library on a background thread."""
        filter_id = self._svo_filters_by_label.get(self.svo_filter_var.get().strip())
        if (not filter_id):
            self.svo_status_label.configure(text=tr("Choose a filter to download."))
            return
        self.svo_download_button.configure(state="disabled")
        self.svo_status_label.configure(text=tr("Downloading {filter} from SVO...").format(filter=filter_id))

        def worker():
            from .photometry import svo
            try:
                svo.download_filter(filter_id, user_filters_root())
                band_key = svo.band_key_for_filter_id(filter_id)
            except svo.SvoError as error:
                self.after(0, self._svo_download_failed, str(error))
                return
            self.after(0, self._svo_download_ready, filter_id, band_key)

        threading.Thread(target=worker, daemon=True).start()

    def _svo_download_ready(self, filter_id: str, band_key: str) -> None:
        self.refresh_output_bands()
        self.conversion_output_band_var.set(band_key)
        self.conversion_method_var.set(self.conversion_method_var.get().strip() or "blackbody")
        self.svo_download_button.configure(state="normal")
        self.update_conversion_field_state()
        self.svo_status_label.configure(
            text=tr("Downloaded {filter}. Output band set to {band}.").format(filter=filter_id, band=band_key)
        )

    def _svo_download_failed(self, message: str) -> None:
        self.svo_download_button.configure(state="normal")
        self.svo_status_label.configure(text=message)

    def refresh_output_bands(self) -> None:
        """Repopulate the output-band picker after the filter library changes."""
        from .photometry import library

        library._discover.cache_clear()
        combo = getattr(self, "conversion_output_combo", None)
        if (combo is not None):
            combo.configure(values=[NO_CONVERSION_LABEL, *available_output_bands(), "custom"])

    def update_model_field_state(self) -> None:
        if (not self.model_dependent_entries):
            return

        mode = self.contamination_mode_var.get().strip()
        state = "normal" if (mode == "gaussian_psf") else "disabled"
        self.model_dependent_entries["gaussian_fwhm"].configure(state=state)
        self.model_dependent_entries["influence_sigma"].configure(state=state)
        self.update_derived_influence_radius()

    def update_derived_influence_radius(self) -> None:
        """Show the outer influence radius implied by the current FWHM and sigma count."""
        label = getattr(self, "derived_influence_label", None)
        if (label is None):
            return

        message = self.derived_influence_message()
        label.configure(text=message)

    def derived_influence_message(self) -> str:
        """Return the translated status line describing the derived influence radius."""
        if (self.contamination_mode_var.get().strip() != "gaussian_psf"):
            return tr("top_hat searches the aperture radius only; no PSF leakage is modelled.")

        try:
            fwhm = float(self.gaussian_fwhm_var.get().strip())
            sigmas = float(self.influence_sigma_var.get().strip())
        except ValueError:
            return tr("Enter a FWHM and a number of sigmas to derive the outer influence radius.")

        if (fwhm <= 0.0 or sigmas <= 0.0):
            return tr("FWHM and number of sigmas must both be greater than zero.")

        sigma = fwhm / GAUSSIAN_FWHM_TO_SIGMA
        return (
            f"sigma = {sigma:.3f}\" (FWHM / 2.355)  ->  "
            f"{tr('outer influence radius')} = {sigmas:g} x {sigma:.3f}\" = {sigma * sigmas:.3f}\""
        )

    def toggle_advanced_settings(self) -> None:
        if (self.advanced_settings_var.get()):
            proceed = messagebox.askyesno(
                "Advanced settings warning",
                "These settings are for performance tuning only.\n\n"
                "Bad values can make the tool slower, increase RAM usage, write too often to disk, "
                "or make long runs harder to resume safely.\n\n"
                "Enable advanced settings anyway?"
            )
            if (not proceed):
                self.advanced_settings_var.set(False)

        self.set_advanced_widgets_state()

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------
    def make_project_relative_path(self, path_value: str) -> str:
        path_value = str(path_value).strip().replace("\\", "/")
        if (path_value == ""):
            return ""

        path_obj = Path(path_value).expanduser()
        try:
            if (path_obj.is_absolute()):
                resolved = path_obj.resolve()
            else:
                resolved = (PROJECT_DIR / path_obj).resolve()

            relative = resolved.relative_to(PROJECT_DIR.resolve())
            return relative.as_posix()
        except Exception:
            return path_value

    def resolve_user_path(self, path_value: str) -> Path | None:
        path_value = str(path_value).strip()
        if (path_value == ""):
            return None

        path_obj = Path(path_value).expanduser()
        if (path_obj.is_absolute()):
            return path_obj

        return (PROJECT_DIR / path_obj)

    def resolve_path(self, path_value: str) -> Path:
        path_obj = self.resolve_user_path(path_value)
        if (path_obj is None):
            raise ValueError("Path cannot be empty.")

        return path_obj

    def read_csv_header(self, path_value: str) -> list[str]:
        path_obj = self.resolve_user_path(path_value)
        if (path_obj is None):
            return []

        if (not path_obj.is_file()):
            raise FileNotFoundError(str(path_obj))

        with open(path_obj, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                raise ValueError("The CSV file is empty.")

        return [str(column).strip() for column in header]

    def format_header_list(self, header: list[str], limit: int = 40) -> str:
        shown = header[:limit]
        formatted = "\n".join(f"- {column}" for column in shown)

        if (len(header) > limit):
            formatted += f"\n- ... and {len(header) - limit} more"

        return formatted

    def show_missing_columns_error(
        self,
        title: str,
        path_value: str,
        required_columns: list[str],
        header: list[str],
    ) -> None:
        missing_columns = [column for column in required_columns if column not in header]
        case_matches = []

        for missing_column in missing_columns:
            matches = [column for column in header if (column.lower() == missing_column.lower())]
            for match in matches:
                case_matches.append(f'- configured "{missing_column}", but CSV has "{match}"')

        message = (
            f"{title}\n\n"
            "The configured column names were not found in the CSV header.\n\n"
            "Column names are case-sensitive: ra is different from RA, "
            "and phot_g_mean_mag is different from PHOT_G_MEAN_MAG.\n\n"
            "Missing configured columns:\n"
            + "\n".join(f"- {column}" for column in missing_columns)
            + "\n\n"
        )

        if (case_matches):
            message += (
                "Possible uppercase/lowercase mismatch found:\n"
                + "\n".join(case_matches)
                + "\n\n"
            )

        message += (
            f"CSV file:\n{path_value}\n\n"
            "Available CSV header columns:\n"
            f"{self.format_header_list(header)}"
        )

        messagebox.showerror("Column name mismatch", message)

    def validate_csv_columns(
        self,
        title: str,
        path_value: str,
        required_columns: list[str],
    ) -> bool:
        try:
            header = self.read_csv_header(path_value)
        except FileNotFoundError as exc:
            messagebox.showerror(
                "CSV file not found",
                f"{title}\n\nThe CSV file was not found:\n{exc}"
            )
            return False
        except Exception as exc:
            messagebox.showerror(
                "Could not read CSV header",
                f"{title}\n\nCould not read the CSV header.\n\n{exc}"
            )
            return False

        missing_columns = [column for column in required_columns if column not in header]
        if (missing_columns):
            self.show_missing_columns_error(title, path_value, required_columns, header)
            return False

        return True

    def validate_output_folder_can_be_created(self, folder_value: str) -> bool:
        try:
            folder_path = self.resolve_path(folder_value)
            folder_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as exc:
            messagebox.showerror(
                "Output folder problem",
                "PHOTO-CAT could not create or access the output/index folder.\n\n"
                f"Folder:\n{folder_value}\n\n"
                f"Error:\n{exc}\n\n"
                "Choose a normal writable folder, for example inside Downloads or Documents."
            )
            return False

    def validate_index_folder_ready(self, folder_value: str) -> bool:
        index_path = self.resolve_path(folder_value)
        required_files = [
            "offsets.npy",
            "neighbors_ids.bin",
            "ra.npy",
            "dec.npy",
            "phot_g_mean_mag.npy",
            "real_ids_int.npy",
            "special_ids.npz",
        ]
        missing_files = [name for name in required_files if (not (index_path / name).is_file())]
        if (missing_files):
            messagebox.showerror(
                "Index folder not ready",
                "The selected Query index folder does not contain a complete PHOTO-CAT index.\n\n"
                f"Folder:\n{folder_value}\n\n"
                "Missing files:\n"
                + "\n".join(f"- {name}" for name in missing_files)
                + "\n\nEnable the build step, or select the output folder from a previous successful build."
            )
            return False

        return True

    def get_default_output_dir_for_catalog(self, catalog_path: str) -> str:
        catalog_path = str(catalog_path).strip().replace("\\", "/")
        if (catalog_path == ""):
            return ""

        path_obj = Path(catalog_path).expanduser()
        if (path_obj.is_absolute()):
            catalog_dir = path_obj.parent
        else:
            catalog_dir = Path(catalog_path).parent

        if (str(catalog_dir) in ("", ".")):
            output_dir = Path("output")
        else:
            output_dir = catalog_dir / "output"

        return self.make_project_relative_path(output_dir.as_posix())

    def install_catalog_path_auto_update(self) -> None:
        self.input_catalog_var.trace_add("write", self.schedule_catalog_defaults_from_trace)

    def schedule_catalog_defaults_from_trace(self, *args) -> None:
        if (self._applying_catalog_defaults):
            return

        if (self._catalog_auto_update_after_id is not None):
            try:
                self.after_cancel(self._catalog_auto_update_after_id)
            except Exception:
                pass

        self._catalog_auto_update_after_id = self.after(250, self.apply_catalog_defaults_from_trace)

    def apply_catalog_defaults_from_trace(self) -> None:
        self._catalog_auto_update_after_id = None
        self.apply_catalog_defaults(self.input_catalog_var.get(), update_catalog_var=False)

    def apply_catalog_defaults(self, catalog_path: str, update_catalog_var: bool = True) -> None:
        catalog_path = self.make_project_relative_path(catalog_path)
        if (catalog_path == ""):
            return

        output_dir = self.get_default_output_dir_for_catalog(catalog_path)

        self._applying_catalog_defaults = True
        try:
            if (update_catalog_var):
                self.input_catalog_var.set(catalog_path)

            self.targets_input_var.set(catalog_path)

            if (output_dir != ""):
                self.out_dir_var.set(output_dir)
                self.index_dir_var.set(output_dir)
        finally:
            self._applying_catalog_defaults = False

    def apply_catalog_defaults_from_event(self, event=None) -> None:
        self.apply_catalog_defaults(self.input_catalog_var.get())

    def browse_catalog(self) -> None:
        selected = filedialog.askopenfilename(
            title=tr("Select catalog CSV"),
            filetypes=[(tr("CSV files"), "*.csv"), (tr("All files"), "*.*")]
        )
        if (selected):
            self.apply_catalog_defaults(selected)

    def browse_targets(self) -> None:
        selected = filedialog.askopenfilename(
            title=tr("Select targets CSV"),
            filetypes=[(tr("CSV files"), "*.csv"), (tr("All files"), "*.*")]
        )
        if (selected):
            self.targets_input_var.set(self.make_project_relative_path(selected))

    def browse_conversion_filter(self) -> None:
        selected = filedialog.askopenfilename(
            title=tr("Select filter transmission file"),
            filetypes=[(tr("Filter files"), "*.dat *.txt *.csv"), (tr("All files"), "*.*")]
        )
        if (selected):
            self.conversion_filter_file_var.set(self.make_project_relative_path(selected))

    def browse_out_dir(self) -> None:
        selected = filedialog.askdirectory(title=tr("Select output/index folder"))
        if (selected):
            value = self.make_project_relative_path(selected)
            self.out_dir_var.set(value)
            self.index_dir_var.set(value)

    def browse_index_dir(self) -> None:
        selected = filedialog.askdirectory(title=tr("Select existing index folder"))
        if (selected):
            self.index_dir_var.set(self.make_project_relative_path(selected))

    def use_manual_targets(self) -> None:
        self.targets_input_var.set("")
        self.targets_text.focus_set()

    def parse_manual_targets(self) -> list:
        if (self.targets_text is None):
            return []

        raw_text = self.targets_text.get("1.0", "end").strip()
        if (raw_text == ""):
            return []

        tokens = re.split(r"[\s,;\[\]]+", raw_text)
        targets = []

        for token in tokens:
            token = token.strip().strip("'\"")
            if (token == ""):
                continue

            if (token.lower() in ("null", "none")):
                continue

            if (token.lstrip("+-").isdigit()):
                targets.append(int(token))
            else:
                targets.append(token)

        return targets

    def parse_magnitude_columns(self) -> dict:
        if (self.magnitude_columns_text is None):
            return {}

        raw_text = self.magnitude_columns_text.get("1.0", "end").strip()
        parsed: dict[str, str] = {}
        if (raw_text == ""):
            return parsed

        for line in raw_text.splitlines():
            line = line.strip()
            if (line == ""):
                continue

            if ("=" not in line):
                raise ValueError(
                    f'Invalid magnitude band line: "{line}".\n\nUse band=catalog_column, for example gaia_bp=phot_bp_mean_mag.'
                )

            band, column = line.split("=", 1)
            band = band.strip()
            column = column.strip()
            if (band == "" or column == ""):
                raise ValueError(f'Invalid magnitude band line: "{line}". Band and column cannot be empty.')

            parsed[band] = column

        return parsed

    def parse_contamination_bands(self) -> list[str]:
        raw = self.contamination_bands_var.get().strip()
        if (raw == ""):
            return ["gaia_g"]

        return [item.strip() for item in raw.split(",") if (item.strip() != "")]

    # ------------------------------------------------------------------
    # Pipeline validation / config build
    # ------------------------------------------------------------------
    def validate_with_engine(self, config: dict, validate_query: bool) -> bool:
        """Validate config rules with the real pipeline parser, the single source of truth.

        Ranges, influence >= aperture, positive integers, distinct columns, and the
        contamination-model requirements are all enforced here instead of being
        re-implemented in the GUI. Only the sections that will actually run are
        checked, and no filesystem access happens (validate_runtime=False).
        """
        from .load_config import (
            BUILD_SECTION,
            EXECUTION_SECTION,
            QUERY_SECTION,
            load_config,
        )

        temp_path = PROJECT_DIR / f".photo-cat-gui-validate-{os.getpid()}.yaml"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)

            load_config(BUILD_SECTION, temp_path, validate_runtime=False)
            load_config(EXECUTION_SECTION, temp_path, validate_runtime=False)
            if (validate_query):
                load_config(QUERY_SECTION, temp_path, validate_runtime=False)
        except Exception as exc:
            messagebox.showerror("Invalid configuration", str(exc))
            return False
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass

        return True

    def validate_fields(self) -> bool:
        # Cheap "is it even a number?" pre-parse so the user gets a friendly message
        # before the engine parser reports the same fields with dotted config paths.
        try:
            max_radius = float(self.max_radius_var.get().strip())
            float(self.field_of_view_var.get().strip())
            float(self.delta_mag_var.get().strip())
            int(self.chunk_size_var.get().strip())
            int(self.buffer_flush_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid values", "Radius, delta magnitude, chunk size, and checkpoint interval must be numbers.")
            return False

        fwhm_text = self.gaussian_fwhm_var.get().strip()
        sigma_text = self.influence_sigma_var.get().strip()
        for field_label, text in (("Gaussian FWHM", fwhm_text), ("Number of sigmas", sigma_text)):
            if (text == ""):
                continue
            try:
                float(text)
            except ValueError:
                messagebox.showerror(f"Invalid {field_label}", f"{field_label} must be a number.")
                return False

        # Only a PSF model has an influence radius. top_hat ignores these fields, so
        # values left over from an earlier Gaussian run must not raise a warning
        # about a radius that mode will never search.
        if (self.contamination_mode_var.get().strip() == "gaussian_psf" and fwhm_text != "" and sigma_text != ""):
            influence_radius = (float(fwhm_text) / GAUSSIAN_FWHM_TO_SIGMA) * float(sigma_text)
            if (influence_radius > max_radius):
                proceed = messagebox.askyesno(
                    "Influence radius is larger than build radius",
                    "The derived outer influence radius is larger than the build radius.\n\n"
                    f"FWHM {float(fwhm_text):g}\" gives sigma {float(fwhm_text) / GAUSSIAN_FWHM_TO_SIGMA:.3f}\", "
                    f"and {float(sigma_text):g} sigmas gives {influence_radius:.3f}\" "
                    f"against a build radius of {max_radius:g}\".\n\n"
                    "For the queried targets, PHOTO-CAT will recompute neighbours directly from "
                    "the catalog out to the influence radius (only those targets, not the whole "
                    "catalog), which is slower per target than reading the pre-built index.\n\n"
                    "Continue?"
                )
                if (not proceed):
                    return False

        try:
            magnitude_columns = self.parse_magnitude_columns()
        except ValueError as exc:
            messagebox.showerror("Invalid magnitude bands", str(exc))
            return False

        # Extra contamination bands must have a magnitude-column mapping (gaia_g is implicit).
        contamination_bands = self.parse_contamination_bands()
        available_bands = {"gaia_g", "all"} | set(magnitude_columns.keys())
        unknown_bands = [band for band in contamination_bands if band not in available_bands]
        if (unknown_bands):
            messagebox.showerror(
                "Unknown contamination band",
                "These contamination bands are not defined in Files & columns > Magnitude bands:\n"
                + "\n".join(f"- {band}" for band in unknown_bands)
                + "\n\nAdd a band=catalog_column line for each, or use gaia_g / all."
            )
            return False

        if (self.input_catalog_var.get().strip() == ""):
            messagebox.showerror("Missing catalog", "Select the catalog CSV file.")
            return False

        catalog_path = self.input_catalog_var.get().strip()

        # Delegate ranges, influence >= aperture, distinct columns, positive ints, and
        # contamination-model requirements to the real engine parser.
        try:
            config_preview = self.build_config_from_fields()
        except ValueError as exc:
            messagebox.showerror("Invalid values", str(exc))
            return False

        if (not self.validate_with_engine(config_preview, validate_query=bool(self.run_query_var.get()))):
            return False

        catalog_columns = [
            self.catalog_source_id_column_var.get().strip(),
            self.catalog_ra_column_var.get().strip(),
            self.catalog_dec_column_var.get().strip(),
            self.catalog_mag_column_var.get().strip(),
        ]

        if (self.run_build_var.get()):
            if (not self.validate_csv_columns("Catalog CSV", catalog_path, catalog_columns)):
                return False

        if (self.targets_source_id_column_var.get().strip() == ""):
            messagebox.showerror(
                "Missing targets column name",
                "Targets Source ID column cannot be empty. Use source_id unless your targets CSV uses a different header."
            )
            return False

        if (self.out_dir_var.get().strip() == ""):
            messagebox.showerror("Missing output folder", "Choose an output/index folder.")
            return False

        if (self.index_dir_var.get().strip() == ""):
            messagebox.showerror("Missing index folder", "Choose a query index folder.")
            return False

        if (self.run_build_var.get()):
            if (not self.validate_output_folder_can_be_created(self.out_dir_var.get().strip())):
                return False

        if (self.run_query_var.get() and not self.run_build_var.get()):
            if (not self.validate_index_folder_ready(self.index_dir_var.get().strip())):
                return False

        if (self.run_query_var.get() and self.run_build_var.get()):
            out_dir_normalized = self.resolve_path(self.out_dir_var.get().strip())
            index_dir_normalized = self.resolve_path(self.index_dir_var.get().strip())
            if (out_dir_normalized != index_dir_normalized and not self.validate_index_folder_ready(self.index_dir_var.get().strip())):
                return False

        targets_input = self.targets_input_var.get().strip()
        manual_targets = self.parse_manual_targets()
        if (self.run_query_var.get() and targets_input == "" and not manual_targets):
            messagebox.showerror(
                "Missing targets",
                "Select a Targets CSV file, or leave Targets CSV empty and add at least one source_id in Manual targets."
            )
            return False

        if (self.run_query_var.get() and targets_input != ""):
            target_columns = [self.targets_source_id_column_var.get().strip()]
            if (not self.validate_csv_columns("Targets CSV", targets_input, target_columns)):
                return False

        return True

    def build_config_from_fields(self) -> dict:
        targets_input = self.targets_input_var.get().strip()
        if (targets_input == ""):
            targets_input_value = None
        else:
            targets_input_value = self.make_project_relative_path(targets_input)

        out_dir = self.make_project_relative_path(self.out_dir_var.get())
        index_dir = self.make_project_relative_path(self.index_dir_var.get())
        manual_targets = self.parse_manual_targets()
        catalog_source_id_column = self.catalog_source_id_column_var.get().strip()
        catalog_ra_column = self.catalog_ra_column_var.get().strip()
        catalog_dec_column = self.catalog_dec_column_var.get().strip()
        catalog_mag_column = self.catalog_mag_column_var.get().strip()
        targets_source_id_column = self.targets_source_id_column_var.get().strip()

        magnitude_columns = {"gaia_g": catalog_mag_column}
        magnitude_columns.update(self.parse_magnitude_columns())

        contamination_bands = self.parse_contamination_bands()

        mode = self.contamination_mode_var.get().strip() or "top_hat"
        fwhm_text = self.gaussian_fwhm_var.get().strip()
        gaussian_fwhm = float(fwhm_text) if (fwhm_text != "") else None
        sigma_text = self.influence_sigma_var.get().strip()
        influence_sigma = float(sigma_text) if (sigma_text != "") else None

        output_band = self.conversion_output_band_var.get().strip()
        photometric_conversion = None
        if (output_band not in ("", NO_CONVERSION_LABEL)):
            filter_file = self.conversion_filter_file_var.get().strip() or None
            if (filter_file is not None):
                filter_file = self.make_project_relative_path(filter_file)
            photometric_conversion = {
                "output_band": output_band,
                "conversion_method": self.conversion_method_var.get().strip() or "blackbody",
                "filter_file": filter_file,
                "catalog": self.conversion_catalog_var.get().strip() or "gaia_dr3",
            }

        return {
            "interface": {
                "language": get_language(),
            },
            "build_neighbors_index": {
                "io": {
                    "input_catalog": self.make_project_relative_path(self.input_catalog_var.get()),
                    "out_dir": out_dir,
                    "usecolumns": [
                        catalog_source_id_column,
                        catalog_ra_column,
                        catalog_dec_column,
                        catalog_mag_column,
                    ],
                    "columns": {
                        "source_id": catalog_source_id_column,
                        "ra": catalog_ra_column,
                        "dec": catalog_dec_column,
                        "phot_g_mean_mag": catalog_mag_column,
                    },
                    "magnitude_columns": magnitude_columns,
                },
                "settings": {
                    "use_dask": bool(self.use_dask_var.get()),
                    "calculate_separations": bool(self.calculate_separations_var.get()),
                    "max_radius_arcsec": float(self.max_radius_var.get().strip()),
                    "chunk_size": int(self.chunk_size_var.get().strip()),
                    "buffer_flush_interval": int(self.buffer_flush_var.get().strip()),
                },
            },
            "query_contamination_from_index": {
                "io": {
                    "INDEX_DIR": index_dir,
                    "TARGETS_INPUT": targets_input_value,
                    "targets": manual_targets,
                    "target_source_id_column": targets_source_id_column,
                },
                "settings": {
                    "field_of_view_arcsec": float(self.field_of_view_var.get().strip()),
                    "delta_mag": float(self.delta_mag_var.get().strip()),
                    "include_missing_targets": bool(self.include_missing_targets_var.get()),
                    "contamination_bands": contamination_bands,
                    "photometric_conversion": photometric_conversion,
                    "contamination_model": {
                        "mode": mode,
                        "gaussian_fwhm_arcsec": gaussian_fwhm,
                        "influence_sigma": influence_sigma,
                    },
                },
            },
            "execution": {
                "run_build": bool(self.run_build_var.get()),
                "run_query": bool(self.run_query_var.get()),
                "replace_running_pipeline": bool(self.replace_running_pipeline_var.get()),
            },
        }

    def save_config(self, show_success_message: bool = True) -> bool:
        if (not self.validate_fields()):
            return False

        config = self.build_config_from_fields()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(f"# {tr('PHOTO-CAT configuration')}\n")
                f.write(f"# {tr('You can edit this file manually, or run the starter for your operating system and use the GUI.')}\n")
                f.write(f"# {tr('Selecting Catalog CSV in the GUI auto-fills Targets CSV and the output/index folders.')}\n")
                f.write(f"# {tr('To use manual source_id targets, set TARGETS_INPUT to null and list IDs under targets.')}\n")
                f.write(f"# {tr('Default column names are Gaia-like. Column names are case-sensitive: ra != RA.')}\n")
                f.write(f"# {tr('Change them in the GUI only if your CSV headers differ.')}\n\n")
                yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)
        except Exception as exc:
            messagebox.showerror("Save failed", f"Could not save config.yaml.\n\n{exc}")
            return False

        if (show_success_message):
            messagebox.showinfo("Saved", "config.yaml was saved successfully.")

        return True

    def save_and_run(self) -> None:
        proceed = messagebox.askyesno(
            "Save and run",
            "Are you sure you want to save the current configuration and run the pipeline?"
        )
        if (not proceed):
            return

        if (not self.save_config(show_success_message=False)):
            return

        python_exe = self.find_venv_python()
        if (python_exe is None and not FROZEN):
            messagebox.showerror(
                "Virtual environment missing",
                "The local virtual environment was not found.\n\nRun START_WINDOWS.bat first so it can create the local virtual environment."
            )
            return

        try:
            self.cleanup_finished_pipeline_processes()

            if (self.replace_running_pipeline_var.get()):
                self.close_pipeline_windows()

            self.start_pipeline_window(python_exe)
        except Exception as exc:
            messagebox.showerror("Run failed", f"Could not start the pipeline.\n\n{exc}")

    # ------------------------------------------------------------------
    # Pipeline process management
    # ------------------------------------------------------------------
    def pipeline_environment(self) -> dict:
        env = os.environ.copy()
        env["PHOTO_CAT_PROJECT_DIR"] = str(PROJECT_DIR)
        env["PHOTO_CAT_CONFIG"] = str(CONFIG_PATH)
        env[LANGUAGE_ENVIRONMENT] = get_language()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(SRC_DIR) if (not existing_pythonpath) else str(SRC_DIR) + os.pathsep + existing_pythonpath
        return env

    def start_pipeline_window(self, python_exe: Path) -> None:
        env = self.pipeline_environment()

        if (FROZEN):
            # The frozen executable is the CLI: run the pipeline via its own `run`
            # subcommand in a fresh console, with the saved config passed explicitly.
            command = [sys.executable, "run", "--config", str(CONFIG_PATH)]
            creationflags = subprocess.CREATE_NEW_CONSOLE if (os.name == "nt") else 0
            process = subprocess.Popen(
                command,
                cwd=PROJECT_DIR,
                env=env,
                creationflags=creationflags,
                start_new_session=(os.name != "nt"),
            )
            self.pipeline_processes.append(process)
            return

        if (os.name == "nt"):
            runner_path = PROJECT_DIR / "scripts" / "run_pipeline_windows.bat"
            if (runner_path.is_file()):
                process = subprocess.Popen(
                    ["cmd.exe", "/c", str(runner_path)],
                    cwd=PROJECT_DIR,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                process = subprocess.Popen(
                    [str(python_exe), "-m", "photo_cat.config_and_run"],
                    cwd=PROJECT_DIR,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )

            self.pipeline_processes.append(process)
            return

        runner_path = PROJECT_DIR / "scripts" / "run_pipeline_unix.sh"
        if (runner_path.is_file()):
            try:
                runner_path.chmod(runner_path.stat().st_mode | 0o111)
            except Exception:
                pass

            if (sys.platform == "darwin"):
                self.open_macos_terminal(runner_path, env)
            else:
                self.open_unix_terminal(runner_path, env)
        else:
            process = subprocess.Popen(
                [str(python_exe), "-m", "photo_cat.config_and_run"],
                cwd=PROJECT_DIR,
                env=env,
                start_new_session=True,
            )
            self.pipeline_processes.append(process)

    def open_macos_terminal(self, runner_path: Path, env: dict) -> None:
        session_id = f"{os.getpid()}-{int(time.time() * 1000)}"
        title = f"PHOTO-CAT Pipeline {session_id}"
        command = (
            f"cd {shlex.quote(str(PROJECT_DIR))}; "
            f"export PHOTO_CAT_PROJECT_DIR={shlex.quote(str(PROJECT_DIR))}; "
            f"export PHOTO_CAT_CONFIG={shlex.quote(str(CONFIG_PATH))}; "
            f"export PHOTO_CAT_PIPELINE_TITLE={shlex.quote(title)}; "
            f"bash {shlex.quote(str(runner_path))}"
        )
        escaped_command = (
            command.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\r", "\\r")
            .replace("\n", "\\n")
        )
        escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            'tell application "Terminal"\n'
            f'    set newTab to do script "{escaped_command}"\n'
            f'    set custom title of newTab to "{escaped_title}"\n'
            '    activate\n'
            'end tell\n'
        )
        subprocess.Popen(["osascript", "-e", script], cwd=PROJECT_DIR, env=env)
        self.pipeline_sessions.append(title)

    def open_unix_terminal(self, runner_path: Path, env: dict) -> None:
        runner_cmd = f"bash {shlex.quote(str(runner_path))}"
        terminal_commands = [
            ["x-terminal-emulator", "-e", "bash", "-lc", runner_cmd],
            ["gnome-terminal", "--", "bash", "-lc", runner_cmd],
            ["konsole", "-e", "bash", "-lc", runner_cmd],
            ["xfce4-terminal", "--command", runner_cmd],
            ["mate-terminal", "--", "bash", "-lc", runner_cmd],
            ["xterm", "-e", "bash", "-lc", runner_cmd],
        ]

        for command in terminal_commands:
            try:
                process = subprocess.Popen(command, cwd=PROJECT_DIR, env=env, start_new_session=True)
                self.pipeline_processes.append(process)
                return
            except FileNotFoundError:
                continue

        process = subprocess.Popen(["bash", str(runner_path)], cwd=PROJECT_DIR, env=env, start_new_session=True)
        self.pipeline_processes.append(process)

    def cleanup_finished_pipeline_processes(self) -> None:
        self.pipeline_processes = [process for process in self.pipeline_processes if (process.poll() is None)]

    def terminate_process_tree(self, process: subprocess.Popen) -> None:
        if (process.poll() is not None):
            return

        if (os.name == "nt"):
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return

        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception:
            try:
                process.terminate()
            except Exception:
                pass

    def close_macos_terminal_sessions(self) -> None:
        if (sys.platform != "darwin" or not self.pipeline_sessions):
            return

        for title in list(self.pipeline_sessions):
            escaped_title = title.replace('"', '\\"')
            script = (
                'tell application "Terminal"\n'
                '    repeat with w in windows\n'
                '        repeat with t in tabs of w\n'
                f'            if custom title of t is "{escaped_title}" then\n'
                '                close w\n'
                '                exit repeat\n'
                '            end if\n'
                '        end repeat\n'
                '    end repeat\n'
                'end tell\n'
            )
            subprocess.run(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

        self.pipeline_sessions = []

    def close_pipeline_windows(self) -> None:
        self.cleanup_finished_pipeline_processes()
        for process in list(self.pipeline_processes):
            self.terminate_process_tree(process)
        self.pipeline_processes = []
        self.close_macos_terminal_sessions()

    def on_window_close(self) -> None:
        self.close_pipeline_windows()
        self.destroy()

    def find_venv_python(self) -> Path | None:
        if (os.name == "nt"):
            candidate = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
        else:
            candidate = PROJECT_DIR / ".venv" / "bin" / "python"

        if (candidate.is_file()):
            return candidate

        return None

    def python_executable(self) -> str:
        venv_python = self.find_venv_python()
        if (venv_python is not None):
            return str(venv_python)

        return sys.executable

    # ------------------------------------------------------------------
    # Tool panels (photo-cat subcommands)
    # ------------------------------------------------------------------
    def build_tool_panel(self, parent, spec: dict) -> None:
        title_widget = ttk.Label(parent, text=spec["title"], style="PanelTitle.TLabel")
        title_widget._photocat_tooltip_key = spec["title"]
        title_widget.grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        command_widget = ttk.Label(parent, text=f"Command: photo-cat {spec['command']}", style="Muted.TLabel")
        command_widget._photocat_tooltip_key = spec["title"]
        command_widget.grid(
            row=1, column=0, columnspan=3, sticky="w"
        )
        description_widget = ttk.Label(parent, text=spec["description"], style="Muted.TLabel", wraplength=880, justify="left")
        description_widget._photocat_tooltip_key = spec["title"]
        description_widget.grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(2, 10)
        )

        form = ttk.Frame(parent)
        form.grid(row=3, column=0, columnspan=3, sticky="ew")
        form.columnconfigure(1, weight=1)

        field_states: list[dict] = []
        row = 0
        for field in spec["fields"]:
            state = self.build_tool_field(form, row, field)
            field_states.append(state)
            row += 1
        self.register_result_autofill(spec, field_states)

        run_button = ttk.Button(
            parent,
            text=spec.get("run_label", "Run"),
            style="Accent.TButton",
            command=lambda: self.run_tool(spec, field_states),
        )
        run_button._photocat_tooltip_key = spec["title"]
        run_button.grid(row=4, column=0, sticky="w", pady=(12, 0))

    def build_tool_field(self, form, row: int, field: dict) -> dict:
        kind = field["kind"]
        label = field["label"]
        state = {"field": field}

        if (kind == "bool"):
            var = tk.BooleanVar(value=bool(field.get("default", False)))
            check = ttk.Checkbutton(form, text=label, variable=var)
            check._photocat_tooltip_key = label
            check.grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            state["var"] = var
            return state

        if (kind == "multi_file"):
            label_widget = ttk.Label(form, text=label)
            label_widget._photocat_tooltip_key = label
            label_widget.grid(row=row, column=0, sticky="nw", pady=4)
            text_widget = self.make_text_widget(form, height=3)
            text_widget._photocat_tooltip_key = label
            text_widget.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
            add_button = ttk.Button(
                form,
                text="Add file...",
                command=lambda widget=text_widget, f=field: self.append_path_to_text(widget, f),
            )
            add_button._photocat_tooltip_key = label
            add_button.grid(row=row, column=2, sticky="n", pady=4)
            state["text"] = text_widget
            return state

        var = tk.StringVar(value=str(field.get("default", "")))
        label_widget = ttk.Label(form, text=label)
        label_widget._photocat_tooltip_key = label
        label_widget.grid(row=row, column=0, sticky="w", pady=4)

        if (kind == "choice"):
            combo = ttk.Combobox(form, textvariable=var, values=field["options"], state="readonly", width=24)
            combo._photocat_tooltip_key = label
            combo.grid(row=row, column=1, sticky="w", padx=(10, 8), pady=4)
        elif (kind in {"file_open", "file_save", "dir"}):
            entry = ttk.Entry(form, textvariable=var, width=60)
            entry._photocat_tooltip_key = label
            entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
            browse_button = ttk.Button(
                form,
                text="Browse...",
                command=lambda v=var, f=field: self.browse_for_field(v, f),
            )
            browse_button._photocat_tooltip_key = label
            browse_button.grid(row=row, column=2, pady=4)
        else:
            entry = ttk.Entry(form, textvariable=var, width=28)
            entry._photocat_tooltip_key = label
            entry.grid(row=row, column=1, sticky="w", padx=(10, 8), pady=4)

        state["var"] = var
        return state

    def register_result_autofill(self, spec: dict, field_states: list[dict]) -> None:
        """Connect one result input to its type-aware automatic output fields."""
        result_state = next(
            (state for state in field_states if state["field"].get("autofill") == "result_json"),
            None,
        )
        if (result_state is None):
            return
        output_states = [state for state in field_states if state["field"].get("autofill_output")]
        entry = {
            "var": result_state["var"],
            "last_auto": "",
            "outputs": [
                {"var": state["var"], "last_auto": "", "role": state["field"]["autofill_output"]}
                for state in output_states
            ],
            "selections": {
                state["field"]["label"]: state["var"]
                for state in field_states
                if state["field"]["kind"] == "choice"
            },
            "command": spec["command"],
        }
        self._result_json_fields.append(entry)
        entry["var"].trace_add("write", lambda *_args, item=entry: self.refresh_result_output_entry(item))
        for variable in entry["selections"].values():
            variable.trace_add("write", lambda *_args, item=entry: self.refresh_result_output_entry(item))

    def refresh_result_output_entry(self, entry: dict) -> None:
        """Refresh outputs that are empty or still owned by automatic naming."""
        result_json = entry["var"].get().strip()
        if (result_json == ""):
            return
        selections = {label: variable.get() for label, variable in entry["selections"].items()}
        for output in entry["outputs"]:
            current = output["var"].get().strip()
            if (current != "" and current != output["last_auto"]):
                continue
            suggestion = suggested_result_output(result_json, output["role"], selections)
            output["var"].set(suggestion)
            output["last_auto"] = suggestion

    def browse_for_field(self, var: tk.StringVar, field: dict) -> None:
        kind = field["kind"]
        filetypes = [(tr(label), pattern) for label, pattern in field.get("filetypes", [("All files", "*.*")])]
        if (kind == "dir"):
            selected = filedialog.askdirectory(title=tr(field["label"]))
        elif (kind == "file_save"):
            selected = filedialog.asksaveasfilename(title=tr(field["label"]), filetypes=filetypes)
        else:
            selected = filedialog.askopenfilename(title=tr(field["label"]), filetypes=filetypes)

        if (selected):
            var.set(selected)

    def append_path_to_text(self, text_widget: tk.Text, field: dict) -> None:
        filetypes = [(tr(label), pattern) for label, pattern in field.get("filetypes", [("All files", "*.*")])]
        selected = filedialog.askopenfilename(title=tr(field["label"]), filetypes=filetypes)
        if (not selected):
            return

        existing = text_widget.get("1.0", "end").strip()
        text_widget.delete("1.0", "end")
        lines = [line for line in existing.splitlines() if line.strip()]
        lines.append(selected)
        text_widget.insert("1.0", "\n".join(lines))

    def assemble_tool_argv(self, spec: dict, field_states: list[dict]) -> list[str] | None:
        positionals: list[str] = []
        options: list[str] = []

        for state in field_states:
            field = state["field"]
            kind = field["kind"]
            flag = field.get("flag")
            required = field.get("required", False)
            label = field["label"]

            if (kind == "bool"):
                value = bool(state["var"].get())
                if (field.get("flag_style") == "store_true"):
                    if (value):
                        options.append(flag)
                else:
                    options.append(flag if value else self.negate_flag(flag))
                continue

            if (kind == "multi_file"):
                lines = [line.strip() for line in state["text"].get("1.0", "end").splitlines() if line.strip()]
                if (not lines and required):
                    messagebox.showerror("Missing value", f"{label} requires at least one entry.")
                    return None
                if (flag is None):
                    positionals.extend(lines)
                else:
                    for line in lines:
                        options.extend([flag, line])
                continue

            value = state["var"].get().strip()
            if (value == ""):
                if (required):
                    messagebox.showerror("Missing value", f"{label} is required.")
                    return None
                continue

            if (flag is None):
                positionals.append(value)
            else:
                options.extend([flag, value])

        return [spec["command"], *positionals, *options]

    def negate_flag(self, flag: str) -> str:
        return "--no-" + flag[2:] if flag.startswith("--") else flag

    def run_tool(self, spec: dict, field_states: list[dict]) -> None:
        argv = self.assemble_tool_argv(spec, field_states)
        if (argv is None):
            return

        self.run_cli(argv)

    def cli_command(self, argv: list[str]) -> list[str]:
        """Build the argv to invoke a photo-cat subcommand for the current runtime.

        In a frozen build the executable itself is the CLI entry point, so it is
        called directly; otherwise the interpreter runs the CLI module.
        """
        if (FROZEN):
            return [sys.executable, *argv]
        return [self.python_executable(), "-m", "photo_cat.cli", *argv]

    def run_cli(self, argv: list[str]) -> None:
        command = self.cli_command(argv)
        env = self.pipeline_environment()

        self.append_output(f"$ photo-cat {' '.join(shlex.quote(part) for part in argv)}\n")
        progress_id = self.start_tool_progress(f"photo-cat {argv[0]}")

        def worker():
            try:
                process = subprocess.Popen(
                    command,
                    cwd=PROJECT_DIR,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in process.stdout:
                    self.queue_output(line)
                process.wait()
                self.after(0, self.finish_tool_progress, progress_id, process.returncode == 0)
                # Queued, not scheduled directly: an after(0, append_output) would
                # overtake lines still sitting in the batch buffer and report the
                # exit code above the output it belongs to.
                self.queue_output(tr("[finished with exit code {code}]", code=process.returncode) + "\n\n")
            except Exception as exc:
                self.after(0, self.finish_tool_progress, progress_id, False)
                self.queue_output(tr("[error] {error}", error=exc) + "\n\n")

        threading.Thread(target=worker, daemon=True).start()

    def start_tool_progress(self, label: str) -> int:
        """Insert and animate one progress row for a GUI-launched command."""
        self._tool_progress_counter += 1
        progress_id = self._tool_progress_counter
        tag = f"tool_progress_{progress_id}"
        self._tool_progress[progress_id] = {
            "tag": tag,
            "label": label,
            "started_at": time.monotonic(),
            "frame": 0,
        }
        if (self.output_text is not None):
            self.output_text.configure(state="normal")
            self.output_text.insert("end", tool_progress_text(0, label, 0.0), (tag,))
            self.output_text.insert("end", "\n")
            self.output_text.see("end")
            self.output_text.configure(state="disabled")
        self.after(140, self.animate_tool_progress, progress_id)
        return progress_id

    def animate_tool_progress(self, progress_id: int) -> None:
        """Move one tool-console bar while its subprocess is still active."""
        entry = self._tool_progress.get(progress_id)
        if (entry is None):
            return
        entry["frame"] += 1
        elapsed = time.monotonic() - entry["started_at"]
        self.replace_tool_progress_text(entry["tag"], tool_progress_text(entry["frame"], entry["label"], elapsed))
        self.after(140, self.animate_tool_progress, progress_id)

    def finish_tool_progress(self, progress_id: int, succeeded: bool) -> None:
        """Stop one animation and leave a durable completed or failed row."""
        entry = self._tool_progress.pop(progress_id, None)
        if (entry is None):
            return
        elapsed = time.monotonic() - entry["started_at"]
        status = "completed" if succeeded else "failed"
        self.replace_tool_progress_text(entry["tag"], tool_progress_text(entry["frame"], entry["label"], elapsed, status))

    def replace_tool_progress_text(self, tag: str, text: str) -> None:
        """Replace only the tagged activity row without disturbing command output."""
        if (self.output_text is None):
            return
        ranges = self.output_text.tag_ranges(tag)
        if (len(ranges) < 2):
            return
        start, end = ranges[0], ranges[-1]
        self.output_text.configure(state="normal")
        self.output_text.delete(start, end)
        self.output_text.insert(start, text, (tag,))
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def queue_output(self, text: str) -> None:
        """Buffer one output line for the next batched flush.

        Scheduling a Tk callback per line floods the event queue during a long
        run: the pipeline emits a progress line very frequently, and each
        callback re-enabled the widget, inserted, and forced a scroll redraw via
        see("end"). Batching collapses a burst into one insert and one redraw
        while preserving the text and its order exactly.

        Safe to call from the reader thread: list.append is atomic under the GIL,
        and only the scheduled flush touches Tk.
        """
        self.pending_output.append(text)
        if (self.output_flush_id is None):
            self.output_flush_id = self.after(OUTPUT_FLUSH_INTERVAL_MS, self.flush_output)

    def flush_output(self) -> None:
        """Write every buffered line to the console widget in a single update."""
        self.output_flush_id = None
        if (not self.pending_output):
            return

        batch = "".join(self.pending_output)
        self.pending_output.clear()
        self.append_output(batch)

    def append_output(self, text: str) -> None:
        if (self.output_text is None):
            return

        self.output_text.configure(state="normal")
        self.output_text.insert("end", text)
        self.trim_output()
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def trim_output(self) -> None:
        """Drop the oldest lines once the console exceeds its scrollback limit.

        A long run otherwise accumulates the whole transcript in the widget, and a
        Tk Text slows down as it grows, so the console degrades exactly during the
        runs that produce the most output. Caller manages the widget state.
        """
        if (self.output_text is None):
            return

        # index("end-1c") is "line.column"; the line number is the current line count.
        line_count = int(str(self.output_text.index("end-1c")).split(".")[0])
        if (line_count <= OUTPUT_MAX_LINES):
            return

        cut_to = line_count - OUTPUT_MAX_LINES + 1
        self.output_text.delete("1.0", f"{cut_to}.0")

    def clear_output(self) -> None:
        # Drop buffered lines too, so a clear cannot be undone by a pending flush.
        self.pending_output.clear()

        if (self.output_text is None):
            return

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Tool specifications
    # ------------------------------------------------------------------
    def _is_result_json(self, path: Path) -> bool:
        """Return True when a JSON file looks like a target-result list (starts with '[')."""
        try:
            with open(path, "r", encoding="utf-8") as file:
                head = file.read(64).lstrip()
        except OSError:
            return False
        return head.startswith("[")

    def latest_result_json(self) -> str:
        """Return the newest pipeline-generated result JSON found under the output folders."""
        search_dirs: list[Path] = []
        for variable in (self.out_dir_var, self.index_dir_var):
            resolved = self.resolve_user_path(variable.get())
            if (resolved is not None):
                search_dirs.append(resolved)
        search_dirs.append(PROJECT_DIR / "output")
        search_dirs.append(PROJECT_DIR / "data" / "output")

        newest_path: Path | None = None
        newest_mtime = -1.0
        seen: set[Path] = set()
        for directory in search_dirs:
            try:
                resolved_dir = directory.resolve()
            except OSError:
                continue
            if (resolved_dir in seen or not resolved_dir.is_dir()):
                continue
            seen.add(resolved_dir)
            for path in resolved_dir.rglob("*.json"):
                try:
                    if (not self._is_result_json(path)):
                        continue
                    mtime = path.stat().st_mtime
                except OSError:
                    continue
                if (mtime > newest_mtime):
                    newest_mtime = mtime
                    newest_path = path

        return str(newest_path.resolve()) if (newest_path is not None) else ""

    def refresh_result_json_fields(self) -> None:
        """Point every tool 'Result JSON' field at the last generated result JSON.

        A field is only updated when it is empty or still holds a previously
        auto-detected value, so a path the user typed or browsed to is preserved.
        """
        latest = self.latest_result_json()
        if (latest == ""):
            return
        for entry in self._result_json_fields:
            current = entry["var"].get().strip()
            if (current == "" or current == entry["last_auto"]):
                entry["var"].set(latest)
                entry["last_auto"] = latest
            self.refresh_result_output_entry(entry)

    def spec_summarize(self) -> dict:
        return {
            "command": "summarize",
            "title": "Summarize results",
            "description": "Summarize a PHOTO-CAT query result JSON as text, JSON, or CSV.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "autofill": "result_json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["text", "json", "csv"], "default": "text"},
                {"kind": "file_save", "label": "Output summary file (optional; prints to console if blank)", "flag": "--output", "autofill_output": "summary"},
            ],
        }

    def spec_screen(self) -> dict:
        return {
            "command": "screen",
            "title": "Screen / rank targets",
            "description": "Rank targets by a contamination metric and assign accept / review / reject decisions.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "autofill": "result_json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output screening file (path)", "flag": "--output", "required": True, "autofill_output": "screening"},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["csv", "json", "markdown"], "default": "csv"},
                {"kind": "text", "label": "Metric", "flag": "--metric", "default": "flux_fraction_total_weighted"},
                {"kind": "float", "label": "Accept max percent", "flag": "--accept-max-percent", "default": "5.0"},
                {"kind": "float", "label": "Review max percent", "flag": "--review-max-percent", "default": "20.0"},
            ],
        }

    def spec_plot(self) -> dict:
        return {
            "command": "plot",
            "title": "Plot (SVG / matplotlib)",
            "description": "Write a plot from a PHOTO-CAT query result JSON.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "autofill": "result_json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "choice", "label": "Kind", "flag": "--kind", "options": PLOT_KINDS, "default": "contaminant-counts"},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["svg", "png", "pdf"], "default": "svg"},
                {"kind": "choice", "label": "Backend", "flag": "--backend", "options": ["svg", "matplotlib"], "default": "svg"},
                {"kind": "file_save", "label": "Output image file (path; auto-named next to the result if blank)", "flag": "--output", "autofill_output": "plot"},
            ],
        }

    def spec_publication_plots(self) -> dict:
        return {
            "command": "publication-plots",
            "title": "Publication plots",
            "description": "Generate contaminant-count and separation distributions, and the RA/Dec contamination sky map.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "autofill": "result_json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "float", "label": "Aperture, arcsec", "flag": "--aperture-arcsec", "required": True, "default": "47.0"},
                {"kind": "dir", "label": "Output directory", "flag": "--output-dir", "required": True, "autofill_output": "publication_plots"},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["png", "pdf", "svg"], "default": "png"},
                {"kind": "int", "label": "DPI", "flag": "--dpi", "default": "300"},
            ],
        }

    def spec_report(self) -> dict:
        return {
            "command": "report",
            "title": "Report",
            "description": "Write an HTML, Markdown, or PDF report from a PHOTO-CAT query result JSON.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "autofill": "result_json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["html", "markdown", "pdf"], "default": "html"},
                {"kind": "file_save", "label": "Output report file (path; auto-named next to the result if blank)", "flag": "--output", "autofill_output": "report"},
            ],
        }

    def spec_export(self) -> dict:
        return {
            "command": "export",
            "title": "Export",
            "description": "Export target-result rows to CSV or Parquet.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "autofill": "result_json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output data file (path)", "flag": "--output", "required": True, "autofill_output": "export"},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["csv", "parquet"], "default": "csv"},
            ],
        }

    def spec_validate(self) -> dict:
        return {
            "command": "validate-results",
            "title": "Validate results",
            "description": "Compare PHOTO-CAT predictions with an external reference contamination table.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "autofill": "result_json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "file_open", "label": "Reference CSV", "flag": None, "required": True,
                 "filetypes": [("CSV files", "*.csv"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output (stats JSON)", "flag": "--output", "required": True, "autofill_output": "validation_stats"},
                {"kind": "file_save", "label": "Matched residuals CSV file (optional)", "flag": "--matched-output", "autofill_output": "validation_residuals"},
                {"kind": "text", "label": "Metric", "flag": "--metric", "default": "flux_fraction_total_weighted"},
                {"kind": "text", "label": "Source ID column", "flag": "--source-id-column", "default": "source_id"},
                {"kind": "text", "label": "Reference column", "flag": "--reference-column", "default": "contamination_percent"},
                {"kind": "float", "label": "Threshold percent (optional)", "flag": "--threshold-percent"},
            ],
        }

    def spec_provenance(self) -> dict:
        return {
            "command": "provenance",
            "title": "Catalogue provenance",
            "description": "Capture provenance metadata for a catalogue CSV.",
            "fields": [
                {"kind": "file_open", "label": "Catalog CSV", "flag": None, "required": True,
                 "filetypes": [("CSV files", "*.csv"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output (JSON)", "flag": "--output", "required": True},
                {"kind": "file_open", "label": "ADQL file (optional)", "flag": "--adql-file"},
                {"kind": "text", "label": "Source ID column", "flag": "--source-id-column", "default": "source_id"},
                {"kind": "text", "label": "RA column", "flag": "--ra-column", "default": "ra"},
                {"kind": "text", "label": "Dec column", "flag": "--dec-column", "default": "dec"},
                {"kind": "text", "label": "Magnitude column", "flag": "--mag-column", "default": "phot_g_mean_mag"},
            ],
        }

    def spec_merge_bright_stars(self) -> dict:
        return {
            "command": "merge-bright-stars",
            "title": "Merge bright stars",
            "description": "Merge a Gaia-like base catalogue with a supplemental bright-star table.",
            "fields": [
                {"kind": "file_open", "label": "Base catalog CSV", "flag": None, "required": True,
                 "filetypes": [("CSV files", "*.csv"), ("All files", "*.*")]},
                {"kind": "file_open", "label": "Bright-star catalog CSV", "flag": None, "required": True,
                 "filetypes": [("CSV files", "*.csv"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output (merged CSV)", "flag": "--output", "required": True},
                {"kind": "text", "label": "Source ID column", "flag": "--source-id-column", "default": "source_id"},
                {"kind": "choice", "label": "Prefer on duplicates", "flag": "--prefer", "options": ["bright", "base"], "default": "bright"},
                {"kind": "file_save", "label": "Provenance output (optional)", "flag": "--provenance-output"},
            ],
        }

    def spec_benchmark(self) -> dict:
        return {
            "command": "benchmark",
            "title": "Benchmark pipeline",
            "description": "Run selected pipeline stages using the current config and write benchmark metadata JSON. "
                           "Uses the config.yaml saved by this GUI unless you pick another config file.",
            "fields": [
                {"kind": "file_open", "label": "Config file", "flag": "--config", "default": str(CONFIG_PATH),
                 "filetypes": [("YAML files", "*.yaml *.yml"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output (JSON)", "flag": "--output", "required": True},
                {"kind": "bool", "label": "Run build stage", "flag": "--run-build", "default": True},
                {"kind": "bool", "label": "Run query stage", "flag": "--run-query", "default": True},
            ],
        }

    def spec_benchmark_table(self) -> dict:
        return {
            "command": "benchmark-table",
            "title": "Benchmark table",
            "description": "Render one or more benchmark JSON captures as a Markdown or CSV table.",
            "fields": [
                {"kind": "multi_file", "label": "Benchmark JSON files", "flag": None, "required": True,
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output table file (path)", "flag": "--output", "required": True},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["markdown", "csv"], "default": "markdown"},
            ],
        }

    def spec_reproduce(self) -> dict:
        return {
            "command": "reproduce",
            "title": "Reproduce",
            "description": "Generate reproducible summaries, plots, reports, and a manifest from configs and/or result JSONs.",
            "fields": [
                {"kind": "multi_file", "label": "Config files", "flag": "--config",
                 "filetypes": [("YAML files", "*.yaml *.yml"), ("All files", "*.*")]},
                {"kind": "multi_file", "label": "Result JSON files", "flag": "--result-json",
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "dir", "label": "Output directory", "flag": "--output-dir", "required": True},
                {"kind": "bool", "label": "Run each config before collecting results", "flag": "--run-configs",
                 "flag_style": "store_true", "default": False},
                {"kind": "choice", "label": "Backend", "flag": "--backend", "options": ["svg", "matplotlib"], "default": "svg"},
            ],
        }

    def spec_doctor(self) -> dict:
        return {
            "command": "doctor",
            "title": "Doctor diagnostics",
            "description": "Run environment and configuration diagnostic checks.",
            "run_label": "Run diagnostics",
            "fields": [
                {"kind": "file_open", "label": "Config file (optional)", "flag": "--config", "default": str(CONFIG_PATH),
                 "filetypes": [("YAML files", "*.yaml *.yml"), ("All files", "*.*")]},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["text", "json"], "default": "text"},
            ],
        }

    # ------------------------------------------------------------------
    # Misc actions
    # ------------------------------------------------------------------
    def load_example_config(self) -> None:
        self.config_data = DEFAULT_CONFIG.copy()
        self.load_values_into_fields()

    def show_help(self) -> None:
        messagebox.showinfo("Help", HELP_TEXT_IT if get_language() == "it" else HELP_TEXT)

    def center_window(self) -> None:
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(1180, max(1040, screen_width - 100))
        height = min(840, max(660, screen_height - 120))
        x = max(0, (screen_width // 2) - (width // 2))
        y = max(0, (screen_height // 2) - (height // 2))
        self.geometry(f"{width}x{height}+{x}+{y}")


def main() -> int:
    app = ConfigGui()
    app.mainloop()
    return 0


if (__name__ == "__main__"):
    raise SystemExit(main())
