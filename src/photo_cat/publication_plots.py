# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Contamination distribution and sky-map plot generators."""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from . import __version__
from .index_manifest import atomic_write_json, sha256_file
from .result_products import iter_contaminants, load_result_rows


PUBLICATION_PLOT_SCHEMA_VERSION = 1
# Sky-map contamination classes drawn as uniform points, with crowded targets
# drawn last (on top). Colours use the colourblind-safe Okabe-Ito palette
# (blue -> orange -> vermillion), ordered by increasing contamination.
SKY_MAP_CLASSES: tuple[dict[str, Any], ...] = (
    {"key": "none", "label": "0 contaminants", "color": "#0072B2", "marker": "o", "size": 4.0},
    {"key": "moderate", "label": "1–3 contaminants", "color": "#E69F00", "marker": "o", "size": 4.0},
    {"key": "crowded", "label": ">3 contaminants", "color": "#D55E00", "marker": "o", "size": 4.0},
)
PUBLICATION_HISTOGRAM_COLOR = "#4477AA"


def _coerce_float(value: Any) -> float:
    """Convert a loosely-typed mapping value to float, raising for None/invalid input."""
    return float(value)


def _matplotlib_pyplot():
    """Load the non-interactive plotting backend with a direct installation hint."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ImportError("Plot generation requires matplotlib.") from error
    return plt


def _contaminant_count_distribution(rows: Iterable[dict[str, Any]]) -> np.ndarray:
    """Return exact frequencies for every integer contaminant count."""
    frequencies = Counter(max(int(row.get("num_contaminants") or 0), 0) for row in rows)
    maximum = max(frequencies, default=0)
    return np.asarray([frequencies.get(value, 0) for value in range(maximum + 1)], dtype=np.int64)


def _separation_distribution(rows: Iterable[dict[str, Any]], bin_width_arcsec: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Bin contaminant separations without materializing millions of values."""
    if (not math.isfinite(bin_width_arcsec) or bin_width_arcsec <= 0.0):
        raise ValueError("bin_width_arcsec must be a positive finite number.")
    frequencies: Counter[int] = Counter()
    for contaminant in iter_contaminants(rows):
        try:
            separation = _coerce_float(contaminant.get("sep_arcsec"))
        except (TypeError, ValueError):
            continue
        if (math.isfinite(separation) and separation >= 0.0):
            frequencies[int(separation / bin_width_arcsec)] += 1
    maximum_bin = max(frequencies, default=0)
    counts = np.asarray([frequencies.get(index, 0) for index in range(maximum_bin + 1)], dtype=np.int64)
    edges = np.arange(maximum_bin + 2, dtype=np.float64) * bin_width_arcsec
    return counts, edges


def _save_figure(fig, path: Path, dpi: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    return str(path)


def _contaminant_count_plot(rows: list[dict[str, Any]], aperture_arcsec: float, destination: Path, dpi: int) -> str:
    """Generate the contaminant-count distribution for one configured aperture."""
    plt = _matplotlib_pyplot()
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    frequencies = _contaminant_count_distribution(rows)
    edges = np.arange(frequencies.size + 1, dtype=np.float64) - 0.5
    ax.stairs(
        frequencies,
        edges,
        label=f'{aperture_arcsec:g}"',
        color=PUBLICATION_HISTOGRAM_COLOR,
        linewidth=1.8,
    )
    # Linear count axis, logarithmic star axis.
    ax.set_yscale("log")
    ax.set_xlabel("Number of contaminants")
    ax.set_ylabel("Number of Stars")
    ax.tick_params(axis="both", which="both", labelsize=11)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.2, which="both")
    saved = _save_figure(fig, destination, dpi)
    plt.close(fig)
    return saved


def _separation_plot(rows: list[dict[str, Any]], destination: Path, dpi: int) -> str:
    """Generate the angular-separation distribution with 1-arcsec bins."""
    plt = _matplotlib_pyplot()
    counts, edges = _separation_distribution(rows)

    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    ax.stairs(counts, edges, fill=True, color=PUBLICATION_HISTOGRAM_COLOR, alpha=0.9, label="Contaminants")
    if (np.any(counts > 0)):
        ax.set_yscale("log")
    ax.set_xlabel("Separation (arcsec)")
    ax.set_ylabel("Number of contaminants")
    ax.tick_params(axis="both", which="both", labelsize=11)
    ax.grid(alpha=0.2, which="both")
    ax.legend(fontsize=10)
    saved = _save_figure(fig, destination, dpi)
    plt.close(fig)
    return saved


def _sky_class(count: int) -> int:
    if (count <= 0):
        return 0
    return 1 if count <= 3 else 2


def _contamination_sky_map(rows: list[dict[str, Any]], destination: Path, dpi: int) -> str:
    """Generate the RA/Dec contamination sky map."""
    plt = _matplotlib_pyplot()
    grouped: list[tuple[list[float], list[float]]] = [([], []), ([], []), ([], [])]
    for row in rows:
        try:
            ra = _coerce_float(row.get("ra")) % 360.0
            dec = _coerce_float(row.get("dec"))
        except (TypeError, ValueError):
            continue
        if (not math.isfinite(ra) or not math.isfinite(dec) or dec < -90.0 or dec > 90.0):
            continue
        index = _sky_class(max(int(row.get("num_contaminants") or 0), 0))
        grouped[index][0].append(ra)
        grouped[index][1].append(dec)

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    for (ra_values, dec_values), style in zip(grouped, SKY_MAP_CLASSES):
        ax.scatter(
            ra_values,
            dec_values,
            s=style["size"],
            c=style["color"],
            marker=style["marker"],
            label=style["label"],
            alpha=0.72,
            linewidths=0,
            rasterized=True,
        )
    ax.set_xlim(0.0, 360.0)
    ax.set_ylim(-90.0, 90.0)
    ax.set_xlabel("RA [deg]")
    ax.set_ylabel("Dec [deg]")
    ax.tick_params(axis="both", which="both", labelsize=11)
    ax.grid(alpha=0.15)
    ax.legend(loc="upper right", fontsize=10, markerscale=2.0)
    saved = _save_figure(fig, destination, dpi)
    plt.close(fig)
    return saved


def generate_publication_plots(
    result_json: str | Path,
    output_dir: str | Path,
    *,
    aperture_arcsec: float,
    output_format: str = "png",
    dpi: int = 300,
) -> dict[str, Any]:
    """Generate contamination plots and a checksummed reproducibility manifest."""
    normalized_format = output_format.lower().lstrip(".")
    if (normalized_format not in {"png", "pdf", "svg"}):
        raise ValueError("Plot format must be one of: png, pdf, svg.")
    if (dpi <= 0):
        raise ValueError("Plot DPI must be a positive integer.")
    if (not math.isfinite(aperture_arcsec) or aperture_arcsec <= 0.0):
        raise ValueError("Plot aperture_arcsec must be a positive finite number.")
    result_path = Path(result_json)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    rows = load_result_rows(result_path)

    count_plot = _contaminant_count_plot(
        rows,
        aperture_arcsec,
        destination / f"contaminant_count_distribution.{normalized_format}",
        dpi,
    )
    separation_plot = _separation_plot(
        rows,
        destination / f"separation_distribution.{normalized_format}",
        dpi,
    )
    sky_map = _contamination_sky_map(
        rows,
        destination / f"contamination_sky_map.{normalized_format}",
        dpi,
    )
    products = {
        "contaminant_count_distribution": count_plot,
        "separation_distribution": separation_plot,
        "contamination_sky_map": sky_map,
    }
    payload: dict[str, Any] = {
        "schema_version": PUBLICATION_PLOT_SCHEMA_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "photo_cat_version": __version__,
        "inputs": {
            "result_json": str(result_path.resolve()),
            "result_sha256": sha256_file(result_path),
        },
        "settings": {"format": normalized_format, "dpi": dpi, "aperture_arcsec": aperture_arcsec},
        "plots": {
            "contaminant_count_distribution": {"path": count_plot, "x_scale": "linear", "y_scale": "log", "aperture_arcsec": aperture_arcsec},
            "separation_distribution": {"path": separation_plot, "y_scale": "log", "bin_width_arcsec": 1.0, "aperture_arcsec": aperture_arcsec},
            "contamination_sky_map": {"path": sky_map, "encoding": list(SKY_MAP_CLASSES), "palette": "colourblind_safe"},
        },
    }
    for key, path in products.items():
        payload["plots"][key]["sha256"] = sha256_file(path)
    manifest_path = destination / "publication_plots_manifest.json"
    atomic_write_json(manifest_path, payload)
    payload["manifest_path"] = str(manifest_path)
    return payload
