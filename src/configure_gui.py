#!/usr/bin/env python3
"""
Small beginner-friendly GUI for editing config.yaml.

This script is intentionally simple and uses tkinter from the Python standard
library. PyYAML is installed by install.py through requirements.txt.
"""

import csv
import os
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yaml


SRC_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SRC_DIR.parent
CONFIG_PATH = PROJECT_DIR / "config.yaml"
PROJECT_DISPLAY_NAME = "PHOTO-CAT - Photometric Contamination Analyzer Tool"
PROJECT_SHORT_NAME = "PHOTO-CAT"


DEFAULT_CONFIG = {
    "build_neighbors_index": {
        "io": {
            "input_catalog": "data/example_catalog.csv",
            "out_dir": "data/output",
            "KDTREE_FILENAME": "ckdtree.pkl",
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
        },
    },
    "execution": {
        "run_build": True,
        "run_query": True,
    },
}


HELP_TEXT = """Basic usage:

1. Select your catalog CSV.
2. The GUI automatically sets:
   - Targets CSV to the same file.
   - Output/index folder to an output folder next to the catalog.
   - Query index folder to the same output/index folder.
3. Click Save + run.

Default Gaia-like column names:
Catalog CSV: source_id, ra, dec, phot_g_mean_mag
Targets CSV: source_id

If your catalog uses different names, change the column fields in the GUI to match your CSV header exactly.
Column names are case-sensitive: ra is different from RA, and phot_g_mean_mag is different from PHOT_G_MEAN_MAG.
For example, if your RA column is named RA_ICRS instead of ra, set the RA column field to RA_ICRS.

Targets:
- Easiest mode: leave Targets CSV equal to the catalog CSV.
- CSV mode: select a different CSV containing the configured target source_id column.
- Manual mode: empty the Targets CSV field and write source_ids in the manual list.

Tip for beginners:
Use the default example files first. They are already configured and should run immediately.
"""


class ConfigGui(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"{PROJECT_DISPLAY_NAME} - Configurator")
        self.resizable(True, True)
        self.minsize(900, 620)
        self.dark_mode = self.detect_dark_mode()
        self.colors = self.get_theme_colors()
        self.configure(bg=self.colors["window_bg"])
        self.create_styles()
        self.config_data = self.load_config()

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
        self.chunk_size_var = tk.StringVar()
        self.buffer_flush_var = tk.StringVar()
        self.use_dask_var = tk.BooleanVar()
        self.advanced_settings_var = tk.BooleanVar(value=False)
        self.advanced_entry_widgets = []
        self.calculate_separations_var = tk.BooleanVar()
        self.run_build_var = tk.BooleanVar()
        self.run_query_var = tk.BooleanVar()
        self.targets_text = None
        self.catalog_entry = None

        self.create_widgets()
        self.load_values_into_fields()
        self.set_advanced_widgets_state()
        self.center_window()

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
                "entry_bg": "#17181b",
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
            "entry_bg": "#ffffff",
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
        self.style.configure("TLabelframe", background=colors["window_bg"], foreground=colors["text"], bordercolor=colors["border"])
        self.style.configure("TLabelframe.Label", background=colors["window_bg"], foreground=colors["text"], font=("Segoe UI", 10, "bold"))
        self.style.configure("TLabel", background=colors["window_bg"], foreground=colors["text"])
        self.style.configure("Muted.TLabel", background=colors["window_bg"], foreground=colors["muted"])
        self.style.configure("Warning.TLabel", background=colors["window_bg"], foreground=colors["warning"])
        self.style.configure("Title.TLabel", background=colors["window_bg"], foreground=colors["text"], font=("Segoe UI", 13, "bold"))
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
            "Visible.TNotebook",
            background=colors["window_bg"],
            borderwidth=0,
            tabmargins=(0, 3, 0, 0),
        )
        self.style.configure(
            "Visible.TNotebook.Tab",
            background=colors["tab_bg"],
            foreground=colors["text"],
            bordercolor=colors["border"],
            lightcolor=colors["border"],
            darkcolor=colors["border"],
            padding=(13, 6),
            font=("Segoe UI", 9, "bold"),
        )
        self.style.map(
            "Visible.TNotebook.Tab",
            background=[("selected", colors["panel_bg"]), ("active", colors["tab_active"]), ("!selected", colors["tab_bg"])],
            foreground=[("selected", colors["text"]), ("active", colors["text"]), ("!selected", colors["muted"])],
        )
        self.style.configure(
            "TabNote.TLabel",
            background=colors["window_bg"],
            foreground=colors["muted"],
            font=("Segoe UI", 9),
        )

    def create_scrollable_tab(self, notebook) -> tuple[ttk.Frame, ttk.Frame]:
        outer = ttk.Frame(notebook)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(
            outer,
            borderwidth=0,
            highlightthickness=0,
            background=self.colors["window_bg"],
        )
        content = ttk.Frame(canvas, padding=10)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        def update_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event):
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.grid(row=0, column=0, sticky="nsew")

        def on_mousewheel(event):
            if (event.delta != 0):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_linux_scroll_up(event):
            canvas.yview_scroll(-3, "units")

        def on_linux_scroll_down(event):
            canvas.yview_scroll(3, "units")

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

    def create_widgets(self) -> None:
        self.geometry("1080x820")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(2, weight=1)

        title = ttk.Label(
            root,
            text=PROJECT_DISPLAY_NAME,
            style="Title.TLabel"
        )
        title.grid(row=0, column=0, sticky="w", pady=(0, 4))

        intro = ttk.Label(
            root,
            text="Choose the catalog, check the auto-filled paths, then click Save + run.",
            style="Muted.TLabel"
        )
        intro.grid(row=1, column=0, sticky="w", pady=(0, 8))

        notebook = ttk.Notebook(root, style="Visible.TNotebook")
        notebook.grid(row=2, column=0, sticky="nsew")

        files_outer, files_tab = self.create_scrollable_tab(notebook)
        settings_outer, settings_tab = self.create_scrollable_tab(notebook)
        options_outer, options_tab = self.create_scrollable_tab(notebook)

        notebook.add(files_outer, text="Files and columns")
        notebook.add(settings_outer, text="Search settings")
        notebook.add(options_outer, text="Run options")

        for tab in (files_tab, settings_tab, options_tab):
            tab.columnconfigure(1, weight=1)

        self.catalog_entry = self.add_file_row(files_tab, 0, "Catalog CSV", self.input_catalog_var, self.browse_catalog)
        self.catalog_entry.bind("<FocusOut>", self.apply_catalog_defaults_from_event)
        self.catalog_entry.bind("<Return>", self.apply_catalog_defaults_from_event)

        catalog_columns = ttk.LabelFrame(files_tab, text="Catalog column names", padding=8)
        catalog_columns.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        catalog_columns.columnconfigure(1, weight=1)
        catalog_columns.columnconfigure(3, weight=1)

        catalog_columns_note = ttk.Label(
            catalog_columns,
            text=(
                "Default Gaia-like names are pre-filled. Change them only if your CSV headers are different. "
                "The names must match the catalog CSV exactly, including uppercase/lowercase."
            ),
            style="Muted.TLabel",
            wraplength=900,
            justify="left"
        )
        catalog_columns_note.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        self.add_entry_row(catalog_columns, 1, "Catalog Source ID column", self.catalog_source_id_column_var, column_offset=0)
        self.add_entry_row(catalog_columns, 1, "Catalog RA column", self.catalog_ra_column_var, column_offset=2)
        self.add_entry_row(catalog_columns, 2, "Catalog Dec column", self.catalog_dec_column_var, column_offset=0)
        self.add_entry_row(catalog_columns, 2, "Catalog magnitude column", self.catalog_mag_column_var, column_offset=2)

        self.add_file_row(files_tab, 2, "Targets CSV", self.targets_input_var, self.browse_targets)

        target_columns = ttk.LabelFrame(files_tab, text="Targets column name", padding=8)
        target_columns.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        target_columns.columnconfigure(1, weight=1)

        target_columns_note = ttk.Label(
            target_columns,
            text=(
                "Default target column is source_id. Change it only if your targets CSV uses another header. "
                "This is case-sensitive. Manual targets ignore this field."
            ),
            style="Muted.TLabel",
            wraplength=900,
            justify="left"
        )
        target_columns_note.grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 5))

        self.add_entry_row(target_columns, 1, "Targets Source ID column", self.targets_source_id_column_var)

        self.add_folder_row(files_tab, 4, "Output/index folder", self.out_dir_var, self.browse_out_dir)
        self.add_folder_row(files_tab, 5, "Query index folder", self.index_dir_var, self.browse_index_dir)

        manual_targets = ttk.LabelFrame(files_tab, text="Manual targets", padding=8)
        manual_targets.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        manual_targets.columnconfigure(0, weight=1)

        manual_targets_label = ttk.Label(
            manual_targets,
            text=(
                "Optional. Leave Targets CSV empty/null to use this source_id list instead. "
                "Use one source_id per line, or separate them with commas."
            ),
            style="Muted.TLabel",
            wraplength=900,
            justify="left"
        )
        manual_targets_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 5))

        self.targets_text = tk.Text(
            manual_targets,
            width=88,
            height=3,
            wrap="none",
            bg=self.colors["entry_bg"],
            fg=self.colors["text"],
            insertbackground=self.colors["text"],
            selectbackground=self.colors["accent"],
            selectforeground="#ffffff",
            relief="solid",
            borderwidth=1,
        )
        self.targets_text.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Button(
            manual_targets,
            text="Use manual list",
            command=self.use_manual_targets
        ).grid(row=1, column=1, sticky="n")

        self.add_entry_row(settings_tab, 0, "Max build radius, arcsec", self.max_radius_var)
        self.add_entry_row(settings_tab, 1, "Query field of view, arcsec", self.field_of_view_var)
        self.add_entry_row(settings_tab, 2, "Delta magnitude", self.delta_mag_var)

        settings_note = ttk.Label(
            settings_tab,
            text=(
                "The query field of view should normally be equal to or smaller than the max build radius. "
                "The default query field of view is 47 arcsec."
            ),
            style="Muted.TLabel",
            wraplength=900,
            justify="left"
        )
        settings_note.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 8))

        advanced = ttk.LabelFrame(settings_tab, text="Advanced performance settings", padding=8)
        advanced.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        advanced.columnconfigure(1, weight=1)

        advanced_warning = ttk.Label(
            advanced,
            text=(
                "Leave these locked unless you know what you are doing. Wrong values can make the tool "
                "slower, use too much RAM, write too often to disk, or make long runs harder to resume safely."
            ),
            style="Warning.TLabel",
            wraplength=900,
            justify="left"
        )
        advanced_warning.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Checkbutton(
            advanced,
            text="Enable advanced settings",
            variable=self.advanced_settings_var,
            command=self.toggle_advanced_settings
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 6))

        chunk_size_entry = self.add_entry_row(advanced, 2, "Chunk size", self.chunk_size_var)
        buffer_flush_entry = self.add_entry_row(advanced, 3, "Buffer flush / checkpoint every N chunks", self.buffer_flush_var)
        self.advanced_entry_widgets = [chunk_size_entry, buffer_flush_entry]

        checks = ttk.LabelFrame(options_tab, text="Options", padding=8)
        checks.grid(row=0, column=0, columnspan=3, sticky="ew")

        ttk.Checkbutton(checks, text="Use Dask for very large CSV files", variable=self.use_dask_var).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checks, text="Store neighbor separations on disk", variable=self.calculate_separations_var).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checks, text="Run build step", variable=self.run_build_var).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(checks, text="Run query step", variable=self.run_query_var).grid(row=3, column=0, sticky="w", pady=2)

        help_box = ttk.LabelFrame(options_tab, text="Quick help", padding=8)
        help_box.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        quick_help = ttk.Label(
            help_box,
            text=(
                "Recommended workflow:\n"
                "1. Select Catalog CSV in the first tab.\n"
                "2. Check that Targets CSV and output folders were auto-filled correctly.\n"
                "3. Leave the Gaia-like column names unchanged unless your CSV uses different headers.\n"
                "4. Click Save + run."
            ),
            style="Muted.TLabel",
            wraplength=900,
            justify="left"
        )
        quick_help.grid(row=0, column=0, sticky="w")

        buttons = ttk.Frame(root)
        buttons.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        buttons.columnconfigure(4, weight=1)

        ttk.Button(buttons, text="Help", command=self.show_help).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Load example config", command=self.load_example_config).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(buttons, text="Save config.yaml", command=self.save_config).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(buttons, text="Save + run", command=self.save_and_run, style="Accent.TButton").grid(row=0, column=3)

    def add_file_row(self, parent, row: int, label: str, variable: tk.StringVar, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=70)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
        ttk.Button(parent, text="Browse...", command=command).grid(row=row, column=2, pady=4)
        return entry

    def add_folder_row(self, parent, row: int, label: str, variable: tk.StringVar, command) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=variable, width=70).grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
        ttk.Button(parent, text="Browse...", command=command).grid(row=row, column=2, pady=4)

    def add_entry_row(self, parent, row: int, label: str, variable: tk.StringVar, column_offset: int = 0):
        ttk.Label(parent, text=label).grid(row=row, column=column_offset, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable, width=22)
        entry.grid(row=row, column=column_offset + 1, sticky="w", padx=(10, 18), pady=4)
        return entry

    def load_values_into_fields(self) -> None:
        build_io = self.config_data["build_neighbors_index"]["io"]
        build_settings = self.config_data["build_neighbors_index"]["settings"]
        query_io = self.config_data["query_contamination_from_index"]["io"]
        query_settings = self.config_data["query_contamination_from_index"]["settings"]
        execution = self.config_data["execution"]
        build_columns = self.get_catalog_columns_from_io(build_io)

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
        self.delta_mag_var.set(str(query_settings.get("delta_mag", 5)))
        self.chunk_size_var.set(str(build_settings.get("chunk_size", 10000)))
        self.buffer_flush_var.set(str(build_settings.get("buffer_flush_interval", 200)))
        self.use_dask_var.set(bool(build_settings.get("use_dask", True)))
        self.calculate_separations_var.set(bool(build_settings.get("calculate_separations", False)))
        self.run_build_var.set(bool(execution.get("run_build", True)))
        self.run_query_var.set(bool(execution.get("run_query", True)))
        self.advanced_settings_var.set(False)
        self.set_manual_targets_text(query_io.get("targets", []) or [])
        self.set_advanced_widgets_state()

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

    def set_advanced_widgets_state(self) -> None:
        state = "normal" if (self.advanced_settings_var.get()) else "disabled"

        for widget in self.advanced_entry_widgets:
            widget.configure(state=state)

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

    def make_project_relative_path(self, path_value: str) -> str:
        path_value = str(path_value).strip().replace("\\", "/")
        if (path_value == ""):
            return ""

        path_obj = Path(path_value)
        try:
            resolved = path_obj.resolve()
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

        catalog_dir = Path(catalog_path).parent
        if (str(catalog_dir) in ("", ".")):
            output_dir = Path("output")
        else:
            output_dir = catalog_dir / "output"

        return self.make_project_relative_path(output_dir.as_posix())

    def apply_catalog_defaults(self, catalog_path: str) -> None:
        catalog_path = self.make_project_relative_path(catalog_path)
        if (catalog_path == ""):
            return

        output_dir = self.get_default_output_dir_for_catalog(catalog_path)
        self.input_catalog_var.set(catalog_path)
        self.targets_input_var.set(catalog_path)

        if (output_dir != ""):
            self.out_dir_var.set(output_dir)
            self.index_dir_var.set(output_dir)

    def apply_catalog_defaults_from_event(self, event=None) -> None:
        self.apply_catalog_defaults(self.input_catalog_var.get())

    def browse_catalog(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select catalog CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if (selected):
            self.apply_catalog_defaults(selected)

    def browse_targets(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select targets CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if (selected):
            self.targets_input_var.set(self.make_project_relative_path(selected))

    def browse_out_dir(self) -> None:
        selected = filedialog.askdirectory(title="Select output/index folder")
        if (selected):
            value = self.make_project_relative_path(selected)
            self.out_dir_var.set(value)
            self.index_dir_var.set(value)

    def browse_index_dir(self) -> None:
        selected = filedialog.askdirectory(title="Select existing index folder")
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

    def validate_fields(self) -> bool:
        try:
            max_radius = float(self.max_radius_var.get().strip())
            field_of_view = float(self.field_of_view_var.get().strip())
            delta_mag = float(self.delta_mag_var.get().strip())
            chunk_size = int(self.chunk_size_var.get().strip())
            buffer_flush = int(self.buffer_flush_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid values", "Radius, delta magnitude, chunk size, and checkpoint interval must be numbers.")
            return False

        if (max_radius <= 0 or field_of_view <= 0):
            messagebox.showerror("Invalid values", "Radius values must be greater than 0.")
            return False

        if (field_of_view > max_radius):
            proceed = messagebox.askyesno(
                "Field of view is larger than build radius",
                "The query field of view is larger than the build radius.\n\n"
                "Usually max build radius should be equal to or larger than query field of view.\n\n"
                "Save anyway?"
            )
            if (not proceed):
                return False

        if (chunk_size <= 0 or buffer_flush <= 0):
            messagebox.showerror("Invalid values", "Chunk size and checkpoint interval must be greater than 0.")
            return False

        if (delta_mag < 0):
            messagebox.showerror("Invalid values", "Delta magnitude cannot be negative.")
            return False

        if (self.input_catalog_var.get().strip() == ""):
            messagebox.showerror("Missing catalog", "Select the catalog CSV file.")
            return False

        catalog_path = self.input_catalog_var.get().strip()

        catalog_columns = [
            self.catalog_source_id_column_var.get().strip(),
            self.catalog_ra_column_var.get().strip(),
            self.catalog_dec_column_var.get().strip(),
            self.catalog_mag_column_var.get().strip(),
        ]
        if (any(column == "" for column in catalog_columns)):
            messagebox.showerror(
                "Missing column names",
                "Catalog column names cannot be empty. Use the default Gaia-like names, or change them to match your CSV."
            )
            return False

        if (len(set(catalog_columns)) != len(catalog_columns)):
            messagebox.showerror(
                "Duplicate column names",
                "Catalog Source ID, RA, Dec, and magnitude columns must be four different CSV columns."
            )
            return False

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

        return {
            "build_neighbors_index": {
                "io": {
                    "input_catalog": self.make_project_relative_path(self.input_catalog_var.get()),
                    "out_dir": out_dir,
                    "KDTREE_FILENAME": "ckdtree.pkl",
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
                },
            },
            "execution": {
                "run_build": bool(self.run_build_var.get()),
                "run_query": bool(self.run_query_var.get()),
            },
        }

    def save_config(self, show_success_message: bool = True) -> bool:
        if (not self.validate_fields()):
            return False

        config = self.build_config_from_fields()
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(f"# {PROJECT_DISPLAY_NAME} configuration\n")
                f.write("# You can edit this file manually, or run the starter for your operating system and use the GUI.\n")
                f.write("# Selecting Catalog CSV in the GUI auto-fills Targets CSV and the output/index folders.\n")
                f.write("# To use manual source_id targets, set TARGETS_INPUT to null and list IDs under targets.\n")
                f.write("# Default column names are Gaia-like. Column names are case-sensitive: ra != RA.\n# Change them in the GUI only if your CSV headers differ.\n\n")
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
        if (python_exe is None):
            messagebox.showerror(
                "Virtual environment missing",
                "The local virtual environment was not found.\n\nRun START_WINDOWS.bat first so it can create the local virtual environment."
            )
            return

        try:
            if (os.name == "nt"):
                runner_path = PROJECT_DIR / "scripts" / "run_pipeline_windows.bat"
                if (runner_path.is_file()):
                    subprocess.Popen(
                        ["cmd.exe", "/c", "start", "PHOTO-CAT Pipeline", str(runner_path)],
                        cwd=PROJECT_DIR
                    )
                else:
                    subprocess.Popen(
                        [str(python_exe), str(SRC_DIR / "config_and_run.py")],
                        cwd=PROJECT_DIR,
                        creationflags=subprocess.CREATE_NEW_CONSOLE
                    )
            else:
                subprocess.Popen([str(python_exe), str(SRC_DIR / "config_and_run.py")], cwd=PROJECT_DIR)

            self.after(250, self.destroy)
        except Exception as exc:
            messagebox.showerror("Run failed", f"Could not start the pipeline.\n\n{exc}")

    def find_venv_python(self) -> Path | None:
        if (os.name == "nt"):
            candidate = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
        else:
            candidate = PROJECT_DIR / ".venv" / "bin" / "python"

        if (candidate.is_file()):
            return candidate

        return None

    def load_example_config(self) -> None:
        self.config_data = DEFAULT_CONFIG.copy()
        self.load_values_into_fields()

    def show_help(self) -> None:
        messagebox.showinfo("Help", HELP_TEXT)

    def center_window(self) -> None:
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        width = min(1080, max(900, screen_width - 100))
        height = min(820, max(620, screen_height - 160))
        x = max(0, (screen_width // 2) - (width // 2))
        y = max(0, (screen_height // 2) - (height // 2))
        self.geometry(f"{width}x{height}+{x}+{y}")


if (__name__ == "__main__"):
    app = ConfigGui()
    app.mainloop()
