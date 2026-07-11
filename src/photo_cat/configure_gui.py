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


PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_DIR = SRC_DIR.parent
CONFIG_PATH = Path(os.environ.get("PHOTO_CAT_CONFIG", str(PROJECT_DIR / "config.yaml"))).resolve()
ASSETS_DIR = PROJECT_DIR / "assets"
PROJECT_DISPLAY_NAME = "PHOTO-CAT - Photometric Contamination Analyzer Tool"
PROJECT_SHORT_NAME = "PHOTO-CAT"


DEFAULT_CONFIG = {
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
            "influence_radius_arcsec": 47.0,
            "delta_mag": 5,
            "include_missing_targets": False,
            "contamination_bands": ["gaia_g"],
            "bandpass_transform_file": None,
            "contamination_model": {
                "mode": "top_hat",
                "gaussian_fwhm_arcsec": None,
                "radial_weight_file": None,
            },
        },
    },
    "execution": {
        "run_build": True,
        "run_query": True,
        "replace_running_pipeline": True,
    },
}


CONTAMINATION_MODES = ["top_hat", "radial_weight", "gaussian_psf", "gaussian_aperture"]
PLOT_KINDS = [
    "contaminant-counts",
    "flux",
    "separations",
    "separations-normalized",
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
3. Click Save + run.

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


class ConfigGui(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(f"{PROJECT_DISPLAY_NAME} - Configurator")
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
        self.influence_radius_var = tk.StringVar()
        self.bandpass_transform_file_var = tk.StringVar()
        self.delta_mag_var = tk.StringVar()
        self.contamination_bands_var = tk.StringVar()
        self.contamination_mode_var = tk.StringVar(value="top_hat")
        self.gaussian_fwhm_var = tk.StringVar()
        self.radial_weight_file_var = tk.StringVar()
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
        self._recolor_hooks = []
        self.logo_label = None
        self.logo_images = {}
        self.theme_button = None
        self.output_text = None
        self.model_dependent_entries = {}

        self.create_widgets()
        self.load_values_into_fields()
        self.install_catalog_path_auto_update()
        self.set_advanced_widgets_state()
        self.update_model_field_state()
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
            self.theme_button.configure(text=self.theme_button_label())

        if (self.current_section is not None):
            self.show_section(self.current_section)

    def toggle_theme(self) -> None:
        self.set_theme(not self.dark_mode)

    def theme_button_label(self) -> str:
        return "Switch to light mode" if self.dark_mode else "Switch to dark mode"

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

        def update_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event):
            canvas.itemconfigure(window_id, width=event.width)

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(outer, orient="vertical", style="Vertical.TScrollbar", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

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

    def add_sidebar_header(self, parent, text: str, row: int) -> None:
        label = ttk.Label(parent, text=text.upper(), style="SidebarHeader.TLabel")
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
        content.columnconfigure(1, weight=1)
        self.section_frames[key] = outer
        return content

    def show_section(self, key: str) -> None:
        frame = self.section_frames.get(key)
        if (frame is None):
            return

        frame.tkraise()
        self.current_section = key

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

        self.theme_button = ttk.Button(header, text=self.theme_button_label(), command=self.toggle_theme)
        self.theme_button.grid(row=0, column=2, rowspan=2, sticky="e")

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
            ("plot", "Plot (SVG)", self.spec_plot),
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
            ("reproduce", "Reproduce paper", self.spec_reproduce_paper),
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
        ttk.Button(buttons, text="Save + run pipeline", command=self.save_and_run, style="Accent.TButton").grid(row=0, column=3)

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
        self.targets_text.grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Button(manual_targets, text="Use manual list", command=self.use_manual_targets).grid(row=1, column=1, sticky="n")

    def build_settings_panel(self, settings_tab) -> None:
        ttk.Label(settings_tab, text="Search settings", style="PanelTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 8)
        )

        self.add_entry_row(settings_tab, 1, "Max build radius, arcsec", self.max_radius_var)
        self.add_entry_row(settings_tab, 2, "Query aperture radius, arcsec", self.field_of_view_var)
        self.add_entry_row(settings_tab, 3, "Outer influence radius, arcsec", self.influence_radius_var)
        self.add_entry_row(settings_tab, 4, "Delta magnitude", self.delta_mag_var)
        self.add_entry_row(settings_tab, 5, "Contamination bands (comma-separated, or all)", self.contamination_bands_var)
        self.add_file_row(settings_tab, 6, "Bandpass profile YAML (optional)", self.bandpass_transform_file_var, self.browse_bandpass_file)

        ttk.Label(
            settings_tab,
            text=(
                "The aperture radius defines the extraction/screening circle. The influence radius can be larger "
                "when a weighted PSF model should include leakage from nearby sources outside that aperture. "
                "Both must be equal to or smaller than the max build radius."
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
                "top_hat keeps the historical catalogue/aperture flux estimate. gaussian_psf and gaussian_aperture "
                "need a Gaussian FWHM. radial_weight needs a CSV of sep_arcsec,weight."
            ),
            style="Muted.TLabel",
            wraplength=880,
            justify="left",
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))

        ttk.Label(model, text="Model mode").grid(row=1, column=0, sticky="w", pady=4)
        mode_combo = ttk.Combobox(
            model,
            textvariable=self.contamination_mode_var,
            values=CONTAMINATION_MODES,
            state="readonly",
            width=22,
        )
        mode_combo.grid(row=1, column=1, sticky="w", padx=(10, 0), pady=4)
        mode_combo.bind("<<ComboboxSelected>>", lambda event: self.update_model_field_state())

        fwhm_entry = self.add_entry_row(model, 2, "Gaussian FWHM, arcsec", self.gaussian_fwhm_var)
        radial_entry = self.add_file_row(model, 3, "Radial weight CSV", self.radial_weight_file_var, self.browse_radial_weight_file)
        self.model_dependent_entries = {"gaussian_fwhm": fwhm_entry, "radial_weight": radial_entry}

        advanced = ttk.LabelFrame(settings_tab, text="Advanced performance settings", padding=8)
        advanced.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(8, 0))
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
            text="Replace running pipeline when Save + run is clicked",
            variable=self.replace_running_pipeline_var,
        ).grid(row=5, column=0, sticky="w", pady=(8, 2))

        ttk.Label(
            checks,
            text=(
                "Enabled: the previous pipeline window opened by this GUI is closed before a new run starts. "
                "Disabled: each Save + run opens a separate pipeline window."
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
                "4. Click Save + run pipeline.\n"
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
        self.influence_radius_var.set(str(query_settings.get("influence_radius_arcsec", query_settings.get("field_of_view_arcsec", 47.0))))
        self.bandpass_transform_file_var.set(str(query_settings.get("bandpass_transform_file") or ""))
        self.delta_mag_var.set(str(query_settings.get("delta_mag", 5)))
        self.contamination_bands_var.set(", ".join(query_settings.get("contamination_bands") or ["gaia_g"]))
        self.contamination_mode_var.set(str(model.get("mode") or "top_hat"))
        self.gaussian_fwhm_var.set("" if (model.get("gaussian_fwhm_arcsec") is None) else str(model.get("gaussian_fwhm_arcsec")))
        self.radial_weight_file_var.set(str(model.get("radial_weight_file") or ""))
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

    def update_model_field_state(self) -> None:
        if (not self.model_dependent_entries):
            return

        mode = self.contamination_mode_var.get().strip()
        fwhm_state = "normal" if (mode in {"gaussian_psf", "gaussian_aperture"}) else "disabled"
        radial_state = "normal" if (mode == "radial_weight") else "disabled"
        self.model_dependent_entries["gaussian_fwhm"].configure(state=fwhm_state)
        self.model_dependent_entries["radial_weight"].configure(state=radial_state)

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

    def browse_bandpass_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select bandpass profile YAML",
            filetypes=[("YAML files", "*.yaml *.yml"), ("All files", "*.*")]
        )
        if (selected):
            self.bandpass_transform_file_var.set(self.make_project_relative_path(selected))

    def browse_radial_weight_file(self) -> None:
        selected = filedialog.askopenfilename(
            title="Select radial weight CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if (selected):
            self.radial_weight_file_var.set(self.make_project_relative_path(selected))

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
            influence_radius = float(self.influence_radius_var.get().strip())
            float(self.field_of_view_var.get().strip())
            float(self.delta_mag_var.get().strip())
            int(self.chunk_size_var.get().strip())
            int(self.buffer_flush_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid values", "Radius, delta magnitude, chunk size, and checkpoint interval must be numbers.")
            return False

        fwhm_text = self.gaussian_fwhm_var.get().strip()
        if (fwhm_text != ""):
            try:
                float(fwhm_text)
            except ValueError:
                messagebox.showerror("Invalid Gaussian FWHM", "Gaussian FWHM must be a number.")
                return False

        if (influence_radius > max_radius):
            proceed = messagebox.askyesno(
                "Influence radius is larger than build radius",
                "The outer influence radius is larger than the build radius.\n\n"
                "The query cannot use neighbours that were not included in the built index.\n\n"
                "Save anyway?"
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
        radial_weight = self.radial_weight_file_var.get().strip() or None
        if (radial_weight is not None):
            radial_weight = self.make_project_relative_path(radial_weight)

        return {
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
                    "influence_radius_arcsec": float(self.influence_radius_var.get().strip()),
                    "delta_mag": float(self.delta_mag_var.get().strip()),
                    "include_missing_targets": bool(self.include_missing_targets_var.get()),
                    "contamination_bands": contamination_bands,
                    "bandpass_transform_file": self.bandpass_transform_file_var.get().strip() or None,
                    "contamination_model": {
                        "mode": mode,
                        "gaussian_fwhm_arcsec": gaussian_fwhm,
                        "radial_weight_file": radial_weight,
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
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = str(SRC_DIR) if (not existing_pythonpath) else str(SRC_DIR) + os.pathsep + existing_pythonpath
        return env

    def start_pipeline_window(self, python_exe: Path) -> None:
        env = self.pipeline_environment()

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
        ttk.Label(parent, text=spec["title"], style="PanelTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )
        ttk.Label(parent, text=f"Command: photo-cat {spec['command']}", style="Muted.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(parent, text=spec["description"], style="Muted.TLabel", wraplength=880, justify="left").grid(
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

        run_button = ttk.Button(
            parent,
            text=spec.get("run_label", "Run"),
            style="Accent.TButton",
            command=lambda: self.run_tool(spec, field_states),
        )
        run_button.grid(row=4, column=0, sticky="w", pady=(12, 0))

    def build_tool_field(self, form, row: int, field: dict) -> dict:
        kind = field["kind"]
        label = field["label"]
        state = {"field": field}

        if (kind == "bool"):
            var = tk.BooleanVar(value=bool(field.get("default", False)))
            ttk.Checkbutton(form, text=label, variable=var).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
            state["var"] = var
            return state

        if (kind == "multi_file"):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="nw", pady=4)
            text_widget = self.make_text_widget(form, height=3)
            text_widget.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
            ttk.Button(
                form,
                text="Add file...",
                command=lambda widget=text_widget, f=field: self.append_path_to_text(widget, f),
            ).grid(row=row, column=2, sticky="n", pady=4)
            state["text"] = text_widget
            return state

        var = tk.StringVar(value=str(field.get("default", "")))
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=4)

        if (kind == "choice"):
            combo = ttk.Combobox(form, textvariable=var, values=field["options"], state="readonly", width=24)
            combo.grid(row=row, column=1, sticky="w", padx=(10, 8), pady=4)
        elif (kind in {"file_open", "file_save", "dir"}):
            entry = ttk.Entry(form, textvariable=var, width=60)
            entry.grid(row=row, column=1, sticky="ew", padx=(10, 8), pady=4)
            ttk.Button(
                form,
                text="Browse...",
                command=lambda v=var, f=field: self.browse_for_field(v, f),
            ).grid(row=row, column=2, pady=4)
        else:
            entry = ttk.Entry(form, textvariable=var, width=28)
            entry.grid(row=row, column=1, sticky="w", padx=(10, 8), pady=4)

        state["var"] = var
        return state

    def browse_for_field(self, var: tk.StringVar, field: dict) -> None:
        kind = field["kind"]
        filetypes = field.get("filetypes", [("All files", "*.*")])
        if (kind == "dir"):
            selected = filedialog.askdirectory(title=field["label"])
        elif (kind == "file_save"):
            selected = filedialog.asksaveasfilename(title=field["label"], filetypes=filetypes)
        else:
            selected = filedialog.askopenfilename(title=field["label"], filetypes=filetypes)

        if (selected):
            var.set(selected)

    def append_path_to_text(self, text_widget: tk.Text, field: dict) -> None:
        filetypes = field.get("filetypes", [("All files", "*.*")])
        selected = filedialog.askopenfilename(title=field["label"], filetypes=filetypes)
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

    def run_cli(self, argv: list[str]) -> None:
        python_exe = self.python_executable()
        command = [python_exe, "-m", "photo_cat.cli", *argv]
        env = self.pipeline_environment()

        self.append_output(f"$ photo-cat {' '.join(shlex.quote(part) for part in argv)}\n")

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
                    self.after(0, self.append_output, line)
                process.wait()
                self.after(0, self.append_output, f"[finished with exit code {process.returncode}]\n\n")
            except Exception as exc:
                self.after(0, self.append_output, f"[error] {exc}\n\n")

        threading.Thread(target=worker, daemon=True).start()

    def append_output(self, text: str) -> None:
        if (self.output_text is None):
            return

        self.output_text.configure(state="normal")
        self.output_text.insert("end", text)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")

    def clear_output(self) -> None:
        if (self.output_text is None):
            return

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Tool specifications
    # ------------------------------------------------------------------
    def _default_result_json(self) -> str:
        candidate = PROJECT_DIR / "output" / "results.json"
        return str(candidate) if candidate.is_file() else ""

    def spec_summarize(self) -> dict:
        return {
            "command": "summarize",
            "title": "Summarize results",
            "description": "Summarize a PHOTO-CAT query result JSON as text, JSON, or CSV.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "default": self._default_result_json(),
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["text", "json", "csv"], "default": "text"},
                {"kind": "file_save", "label": "Output (optional)", "flag": "--output"},
            ],
        }

    def spec_screen(self) -> dict:
        return {
            "command": "screen",
            "title": "Screen / rank targets",
            "description": "Rank targets by a contamination metric and assign accept / review / reject decisions.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "default": self._default_result_json(),
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output", "flag": "--output", "required": True},
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
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "default": self._default_result_json(),
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "choice", "label": "Kind", "flag": "--kind", "options": PLOT_KINDS, "default": "contaminant-counts"},
                {"kind": "choice", "label": "Backend", "flag": "--backend", "options": ["svg", "matplotlib"], "default": "svg"},
                {"kind": "file_save", "label": "Output (optional)", "flag": "--output"},
            ],
        }

    def spec_publication_plots(self) -> dict:
        return {
            "command": "publication-plots",
            "title": "Publication plots",
            "description": "Generate contamination distributions and an accessible sky map for publication.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "default": self._default_result_json(),
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "float", "label": "Aperture, arcsec", "flag": "--aperture-arcsec", "required": True, "default": "47.0"},
                {"kind": "dir", "label": "Output directory", "flag": "--output-dir", "required": True},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["png", "pdf", "svg"], "default": "png"},
                {"kind": "int", "label": "DPI", "flag": "--dpi", "default": "300"},
            ],
        }

    def spec_report(self) -> dict:
        return {
            "command": "report",
            "title": "Report",
            "description": "Write an HTML or Markdown report from a PHOTO-CAT query result JSON.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "default": self._default_result_json(),
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["html", "markdown"], "default": "html"},
                {"kind": "file_save", "label": "Output (optional)", "flag": "--output"},
            ],
        }

    def spec_export(self) -> dict:
        return {
            "command": "export",
            "title": "Export",
            "description": "Export target-result rows to CSV or Parquet.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "default": self._default_result_json(),
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output", "flag": "--output", "required": True},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["csv", "parquet"], "default": "csv"},
            ],
        }

    def spec_validate(self) -> dict:
        return {
            "command": "validate-results",
            "title": "Validate results",
            "description": "Compare PHOTO-CAT predictions with an external reference contamination table.",
            "fields": [
                {"kind": "file_open", "label": "Result JSON", "flag": None, "required": True, "default": self._default_result_json(),
                 "filetypes": [("JSON files", "*.json"), ("All files", "*.*")]},
                {"kind": "file_open", "label": "Reference CSV", "flag": None, "required": True,
                 "filetypes": [("CSV files", "*.csv"), ("All files", "*.*")]},
                {"kind": "file_save", "label": "Output (stats JSON)", "flag": "--output", "required": True},
                {"kind": "file_save", "label": "Matched output (optional)", "flag": "--matched-output"},
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
                {"kind": "file_save", "label": "Output", "flag": "--output", "required": True},
                {"kind": "choice", "label": "Format", "flag": "--format", "options": ["markdown", "csv"], "default": "markdown"},
            ],
        }

    def spec_reproduce_paper(self) -> dict:
        return {
            "command": "reproduce-paper",
            "title": "Reproduce paper",
            "description": "Generate reproducible paper summaries, plots, reports, and a manifest from configs and/or result JSONs.",
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
        messagebox.showinfo("Help", HELP_TEXT)

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
