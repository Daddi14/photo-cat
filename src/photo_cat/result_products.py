# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Summary, plotting, and report helpers for PHOTO-CAT query results."""

from __future__ import annotations

import csv
import html
import json
import math
import statistics
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .index_manifest import atomic_write_json
from .i18n import get_language, tr


SUMMARY_SCHEMA_VERSION = 1
PLOT_KINDS = (
    "contaminant-counts",
    "flux",
    "separations",
    "flux-vs-separation",
    "contamination-vs-magnitude",
    "sky-map",
)
# Sky-map contamination classes, ordered by increasing contamination. Colours use
# the colourblind-safe Okabe-Ito palette (blue -> orange -> vermillion).
SKY_MAP_CLASSES = (
    ("0 contaminants", "#0072B2"),
    ("1–3 contaminants", "#E69F00"),
    (">3 contaminants", "#D55E00"),
)
REPORT_FORMATS = ("html", "markdown", "pdf")
EXPORT_FORMATS = ("csv", "parquet")


def load_result_rows(path: str | Path) -> list[dict[str, Any]]:
    """Load a PHOTO-CAT target-result JSON file."""
    result_path = Path(path)
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Could not read result JSON: {result_path}") from error

    if (not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload)):
        raise ValueError("PHOTO-CAT result JSON must be a list of target-result objects.")

    return payload


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if (result == result) else default


def _int_number(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_number(value: Any) -> float | None:
    """Return a finite float or None without converting missing science values to zero."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _mean(values: list[float]) -> float:
    return float(statistics.fmean(values)) if values else 0.0


def _selected_flux(row: dict[str, Any]) -> float:
    return _number(row.get("flux_fraction_selected", row.get("flux_fraction_extra", 0.0)))


def _all_neighbor_flux(row: dict[str, Any]) -> float:
    return _number(row.get("flux_fraction_all_neighbors", _selected_flux(row)))


def iter_contaminants(rows: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
    """Yield contaminant dictionaries from all rows, ignoring malformed entries."""
    for row in rows:
        contaminants = row.get("contaminants", [])
        if isinstance(contaminants, list):
            for contaminant in contaminants:
                if isinstance(contaminant, dict):
                    yield contaminant


def iter_contaminant_points(rows: Iterable[dict[str, Any]]) -> Iterable[dict[str, float]]:
    """Yield contaminant points with parent-target context for scatter plots."""
    for row in rows:
        target_magnitude = _number(row.get("phot_g_mean_mag"), math.nan)
        for contaminant in iter_contaminants([row]):
            contaminant_magnitude = _number(contaminant.get("phot_g_mean_mag"), math.nan)
            separation = _number(contaminant.get("sep_arcsec"), math.nan)
            if (not math.isfinite(target_magnitude) or not math.isfinite(contaminant_magnitude) or not math.isfinite(separation)):
                continue
            flux_ratio_percent = (10.0 ** (-0.4 * (contaminant_magnitude - target_magnitude))) * 100.0
            yield {
                "target_magnitude": target_magnitude,
                "contaminant_magnitude": contaminant_magnitude,
                "separation_arcsec": separation,
                "flux_ratio_percent": flux_ratio_percent,
                "delta_mag": contaminant_magnitude - target_magnitude,
            }


def summarize_results(rows: list[dict[str, Any]], *, source_path: str | Path | None = None) -> dict[str, Any]:
    """Return stable aggregate statistics for one PHOTO-CAT result table."""
    selected_fluxes = [_selected_flux(row) for row in rows]
    all_neighbor_fluxes = [_all_neighbor_flux(row) for row in rows]
    outside_fluxes = [_number(row.get("flux_fraction_outside_aperture", 0.0)) for row in rows]
    total_weighted_fluxes = [_number(row.get("flux_fraction_total_weighted", _all_neighbor_flux(row))) for row in rows]
    transformed_fluxes = [
        value
        for row in rows
        if (value := _optional_number(row.get("flux_fraction_total_weighted_transformed"))) is not None
    ]
    contaminant_counts = [_int_number(row.get("num_contaminants", row.get("num_contaminants_selected", 0))) for row in rows]
    neighbor_counts = [_int_number(row.get("num_neighbors_in_radius", count)) for row, count in zip(rows, contaminant_counts)]
    outside_neighbor_counts = [_int_number(row.get("num_neighbors_outside_aperture", 0)) for row in rows]
    separations = [_number(contaminant.get("sep_arcsec")) for contaminant in iter_contaminants(rows)]

    target_count = len(rows)
    targets_with_contaminants = sum(1 for count in contaminant_counts if count > 0)
    payload = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "source_result_json": None if source_path is None else str(Path(source_path).resolve()),
        "target_count": target_count,
        "targets_with_contaminants": targets_with_contaminants,
        "targets_without_contaminants": target_count - targets_with_contaminants,
        "total_selected_contaminants": int(sum(contaminant_counts)),
        "total_neighbors_in_radius": int(sum(neighbor_counts)),
        "total_neighbors_outside_aperture": int(sum(outside_neighbor_counts)),
        "selected_flux_fraction_percent": {
            "mean": round(_mean(selected_fluxes), 6),
            "median": round(_median(selected_fluxes), 6),
            "max": round(max(selected_fluxes), 6) if selected_fluxes else 0.0,
        },
        "all_neighbor_flux_fraction_percent": {
            "mean": round(_mean(all_neighbor_fluxes), 6),
            "median": round(_median(all_neighbor_fluxes), 6),
            "max": round(max(all_neighbor_fluxes), 6) if all_neighbor_fluxes else 0.0,
        },
        "outside_aperture_flux_fraction_percent": {
            "mean": round(_mean(outside_fluxes), 6),
            "median": round(_median(outside_fluxes), 6),
            "max": round(max(outside_fluxes), 6) if outside_fluxes else 0.0,
        },
        "total_weighted_flux_fraction_percent": {
            "mean": round(_mean(total_weighted_fluxes), 6),
            "median": round(_median(total_weighted_fluxes), 6),
            "max": round(max(total_weighted_fluxes), 6) if total_weighted_fluxes else 0.0,
        },
        "transformed_total_weighted_flux_fraction_percent": {
            "count": len(transformed_fluxes),
            "mean": round(_mean(transformed_fluxes), 6) if transformed_fluxes else None,
            "median": round(_median(transformed_fluxes), 6) if transformed_fluxes else None,
            "max": round(max(transformed_fluxes), 6) if transformed_fluxes else None,
        },
        "contaminants_per_target": {
            "mean": round(_mean([float(value) for value in contaminant_counts]), 6),
            "median": round(_median([float(value) for value in contaminant_counts]), 6),
            "max": max(contaminant_counts) if contaminant_counts else 0,
        },
        "separation_arcsec": {
            "count": len(separations),
            "median": round(_median(separations), 6),
            "min": round(min(separations), 6) if separations else None,
            "max": round(max(separations), 6) if separations else None,
        },
    }
    return payload


def summary_text(summary: dict[str, Any]) -> str:
    """Render a compact human-readable summary."""
    selected = summary["selected_flux_fraction_percent"]
    all_neighbors = summary["all_neighbor_flux_fraction_percent"]
    outside = summary["outside_aperture_flux_fraction_percent"]
    total_weighted = summary["total_weighted_flux_fraction_percent"]
    transformed = summary["transformed_total_weighted_flux_fraction_percent"]
    counts = summary["contaminants_per_target"]
    lines = [
            tr("PHOTO-CAT result summary"),
            tr("Targets: {value}", value=summary["target_count"]),
            tr("With selected contaminants: {value}", value=summary["targets_with_contaminants"]),
            tr("Without selected contaminants: {value}", value=summary["targets_without_contaminants"]),
            tr("Selected contaminants: {value}", value=summary["total_selected_contaminants"]),
            tr("Neighbours in radius: {value}", value=summary["total_neighbors_in_radius"]),
            tr("Neighbours outside aperture: {value}", value=summary["total_neighbors_outside_aperture"]),
            tr("Selected flux % mean/median/max: {value}", value=f"{selected['mean']}/{selected['median']}/{selected['max']}"),
            tr("All-neighbour flux % mean/median/max: {value}", value=f"{all_neighbors['mean']}/{all_neighbors['median']}/{all_neighbors['max']}"),
            tr("Outside-aperture flux % mean/median/max: {value}", value=f"{outside['mean']}/{outside['median']}/{outside['max']}"),
            tr("Total weighted flux % mean/median/max: {value}", value=f"{total_weighted['mean']}/{total_weighted['median']}/{total_weighted['max']}"),
            tr("Contaminants per target mean/median/max: {value}", value=f"{counts['mean']}/{counts['median']}/{counts['max']}"),
        ]
    if (transformed["count"] > 0):
        lines.append(
            tr(
                "Transformed total weighted flux % mean/median/max: {value}",
                value=f"{transformed['mean']}/{transformed['median']}/{transformed['max']}",
            )
        )
    return "\n".join(lines)


def write_summary(summary: dict[str, Any], output_path: str | Path | None, output_format: str) -> str:
    """Write or return a summary in text, JSON, or CSV form."""
    if output_format == "json":
        if output_path is None:
            return json.dumps(summary, indent=2, sort_keys=True)
        atomic_write_json(output_path, summary)
        return str(output_path)

    if output_format == "csv":
        row = flatten_summary(summary)
        if output_path is None:
            return ",".join(row.keys()) + "\n" + ",".join(str(value) for value in row.values())
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(row))
            writer.writeheader()
            writer.writerow(row)
        return str(destination)

    text = summary_text(summary)
    if output_path is None:
        return text
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text + "\n", encoding="utf-8")
    return str(destination)


def flatten_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested summary metrics into one CSV-friendly row."""
    return {
        "target_count": summary["target_count"],
        "targets_with_contaminants": summary["targets_with_contaminants"],
        "targets_without_contaminants": summary["targets_without_contaminants"],
        "total_selected_contaminants": summary["total_selected_contaminants"],
        "total_neighbors_in_radius": summary["total_neighbors_in_radius"],
        "total_neighbors_outside_aperture": summary["total_neighbors_outside_aperture"],
        "selected_flux_mean": summary["selected_flux_fraction_percent"]["mean"],
        "selected_flux_median": summary["selected_flux_fraction_percent"]["median"],
        "selected_flux_max": summary["selected_flux_fraction_percent"]["max"],
        "all_neighbor_flux_mean": summary["all_neighbor_flux_fraction_percent"]["mean"],
        "all_neighbor_flux_median": summary["all_neighbor_flux_fraction_percent"]["median"],
        "all_neighbor_flux_max": summary["all_neighbor_flux_fraction_percent"]["max"],
        "outside_aperture_flux_mean": summary["outside_aperture_flux_fraction_percent"]["mean"],
        "outside_aperture_flux_median": summary["outside_aperture_flux_fraction_percent"]["median"],
        "outside_aperture_flux_max": summary["outside_aperture_flux_fraction_percent"]["max"],
        "total_weighted_flux_mean": summary["total_weighted_flux_fraction_percent"]["mean"],
        "total_weighted_flux_median": summary["total_weighted_flux_fraction_percent"]["median"],
        "total_weighted_flux_max": summary["total_weighted_flux_fraction_percent"]["max"],
        "transformed_total_weighted_flux_count": summary["transformed_total_weighted_flux_fraction_percent"]["count"],
        "transformed_total_weighted_flux_mean": summary["transformed_total_weighted_flux_fraction_percent"]["mean"],
        "transformed_total_weighted_flux_median": summary["transformed_total_weighted_flux_fraction_percent"]["median"],
        "transformed_total_weighted_flux_max": summary["transformed_total_weighted_flux_fraction_percent"]["max"],
        "contaminants_per_target_mean": summary["contaminants_per_target"]["mean"],
        "contaminants_per_target_median": summary["contaminants_per_target"]["median"],
        "contaminants_per_target_max": summary["contaminants_per_target"]["max"],
        "separation_count": summary["separation_arcsec"]["count"],
        "separation_median": summary["separation_arcsec"]["median"],
        "separation_min": summary["separation_arcsec"]["min"],
        "separation_max": summary["separation_arcsec"]["max"],
    }


def _svg_frame(width: int, height: int, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">\n'
        f'<rect width="100%" height="100%" fill="white"/>\n'
        f'<text x="{width / 2:.1f}" y="24" text-anchor="middle" font-family="sans-serif" font-size="16">{html.escape(title)}</text>\n'
        f"{body}\n</svg>\n"
    )


def _svg_legend(entries: list[tuple[str, str]], x: float, y: float) -> str:
    """Render a small colour legend (swatch + label) at the given top-left position."""
    parts: list[str] = []
    for index, (label, color) in enumerate(entries):
        row_y = y + index * 16
        parts.append(f'<rect x="{x:.1f}" y="{row_y:.1f}" width="11" height="11" fill="{color}"/>')
        parts.append(
            f'<text x="{x + 16:.1f}" y="{row_y + 10:.1f}" font-family="sans-serif" font-size="10">{html.escape(label)}</text>'
        )
    return "\n".join(parts)


def _bar_chart(
    counts: Counter[int],
    title: str,
    x_label: str,
    y_label: str | None = None,
    legend: list[tuple[str, str]] | None = None,
    color: str = "#4477AA",
    width: int = 760,
    height: int = 420,
) -> str:
    plot_left, plot_top, plot_width, plot_height = 70, 48, width - 110, height - 110
    values = sorted(counts)
    if not values:
        values = [0]
        counts = Counter({0: 0})
    max_count = max(counts.values()) or 1
    bar_width = max(1, plot_width / max(len(values), 1))
    body = [
        f'<line x1="{plot_left}" y1="{plot_top + plot_height}" x2="{plot_left + plot_width}" y2="{plot_top + plot_height}" stroke="#333"/>',
        f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_top + plot_height}" stroke="#333"/>',
        f'<text x="{width / 2:.1f}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="12">{html.escape(x_label)}</text>',
    ]
    if (y_label is not None):
        body.append(
            f'<text x="18" y="{plot_top + plot_height / 2:.1f}" transform="rotate(-90 18 {plot_top + plot_height / 2:.1f})" '
            f'text-anchor="middle" font-family="sans-serif" font-size="12">{html.escape(y_label)}</text>'
        )
    for index, value in enumerate(values):
        bar_height = (counts[value] / max_count) * plot_height
        x = plot_left + index * bar_width
        y = plot_top + plot_height - bar_height
        body.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(bar_width - 2, 1):.2f}" height="{bar_height:.2f}" fill="{color}"/>')
        if len(values) <= 20:
            body.append(f'<text x="{x + bar_width / 2:.2f}" y="{plot_top + plot_height + 14}" text-anchor="middle" font-family="sans-serif" font-size="10">{value}</text>')
    body.append(f'<text x="14" y="{plot_top + 12}" font-family="sans-serif" font-size="11">max bin count: {max_count}</text>')
    if (legend is not None):
        body.append(_svg_legend(legend, plot_left + plot_width - 130, plot_top + 4))
    return _svg_frame(width, height, title, "\n".join(body))


def _histogram(
    values: list[float],
    title: str,
    x_label: str,
    bins: int = 20,
    y_label: str | None = None,
    legend: list[tuple[str, str]] | None = None,
) -> str:
    if not values:
        return _bar_chart(Counter(), title, x_label, y_label=y_label, legend=legend)
    low, high = min(values), max(values)
    if low == high:
        return _bar_chart(Counter({int(round(low)): len(values)}), title, x_label, y_label=y_label, legend=legend)
    step = (high - low) / bins
    counts: Counter[int] = Counter()
    for value in values:
        bucket = min(int((value - low) / step), bins - 1)
        counts[bucket] += 1
    labels = {bucket: f"{low + bucket * step:.1f}" for bucket in counts}
    svg = _bar_chart(counts, title, x_label, y_label=y_label, legend=legend)
    for bucket, label in labels.items():
        svg = svg.replace(f">{bucket}</text>", f">{html.escape(label)}</text>")
    return svg


def _separation_histogram(values: list[float], title: str, x_label: str, y_label: str) -> str:
    """Bin contaminant separations into contiguous 1-arcsecond bins."""
    finite = [value for value in values if (value is not None and math.isfinite(value) and value >= 0.0)]
    legend = [("Contaminants", "#4477AA")]
    if (not finite):
        return _bar_chart(Counter(), title, x_label, y_label=y_label, legend=legend)
    maximum_bin = int(max(finite))
    counts: Counter[int] = Counter({bin_index: 0 for bin_index in range(maximum_bin + 1)})
    for value in finite:
        counts[int(value)] += 1
    return _bar_chart(counts, title, x_label, y_label=y_label, legend=legend)


def _scatter(
    points: list[tuple[float, float]],
    title: str,
    x_label: str,
    y_label: str,
    legend: list[tuple[str, str]] | None = None,
    width: int = 760,
    height: int = 420,
) -> str:
    plot_left, plot_top, plot_width, plot_height = 80, 48, width - 125, height - 120
    if (not points):
        return _svg_frame(width, height, title, "<text x=\"80\" y=\"80\" font-family=\"sans-serif\" font-size=\"12\">No contaminant points available.</text>")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if (xmin == xmax):
        xmin -= 0.5
        xmax += 0.5
    if (ymin == ymax):
        ymin -= 0.5
        ymax += 0.5
    body = [
        f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f7f7f7" stroke="#333"/>',
        f'<text x="{width / 2:.1f}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="12">{html.escape(x_label)}</text>',
        f'<text x="18" y="{plot_top + plot_height / 2:.1f}" transform="rotate(-90 18 {plot_top + plot_height / 2:.1f})" text-anchor="middle" font-family="sans-serif" font-size="12">{html.escape(y_label)}</text>',
    ]
    for x_value, y_value in points:
        x = plot_left + ((x_value - xmin) / (xmax - xmin)) * plot_width
        y = plot_top + plot_height - ((y_value - ymin) / (ymax - ymin)) * plot_height
        body.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.2" fill="#4477AA" fill-opacity="0.65"/>')
    if (legend is not None):
        body.append(_svg_legend(legend, plot_left + plot_width - 150, plot_top + 4))
    return _svg_frame(width, height, title, "\n".join(body))


def _severity_style(count: int) -> tuple[str, float, float]:
    """Map a contaminant count to its sky-map colour with a uniform marker size.

    Colours use the colourblind-safe Okabe-Ito palette. Returns
    (hex_colour, svg_radius, matplotlib_area).
    """
    if (count == 0):
        return "#0072B2", 2.4, 8.0
    if (count <= 3):
        return "#E69F00", 2.4, 8.0
    return "#D55E00", 2.4, 8.0


def _sky_map(rows: list[dict[str, Any]], width: int = 760, height: int = 420) -> str:
    plot_left, plot_top, plot_width, plot_height = 60, 48, width - 100, height - 100
    body = [
        f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f7f7f7" stroke="#333"/>',
        f'<text x="{plot_left + plot_width / 2:.1f}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="12">RA [deg]</text>',
        f'<text x="18" y="{plot_top + plot_height / 2:.1f}" transform="rotate(-90 18 {plot_top + plot_height / 2:.1f})" text-anchor="middle" font-family="sans-serif" font-size="12">Dec [deg]</text>',
    ]
    for row in rows:
        ra = _number(row.get("ra"), None)  # type: ignore[arg-type]
        dec = _number(row.get("dec"), None)  # type: ignore[arg-type]
        if ra is None or dec is None:
            continue
        count = _int_number(row.get("num_contaminants", 0))
        color, radius, _ = _severity_style(count)
        x = plot_left + ((ra % 360.0) / 360.0) * plot_width
        y = plot_top + ((90.0 - max(min(dec, 90.0), -90.0)) / 180.0) * plot_height
        body.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.1f}" fill="{color}" fill-opacity="0.85"/>')
    body.append(_svg_legend(list(SKY_MAP_CLASSES), plot_left + plot_width - 130, plot_top + 6))
    return _svg_frame(width, height, "Sky map of stellar contamination", "\n".join(body))


def build_svg_plot(rows: list[dict[str, Any]], kind: str) -> str:
    """Build a dependency-free SVG plot for one result table."""
    if kind == "contaminant-counts":
        counts = Counter(_int_number(row.get("num_contaminants", 0)) for row in rows)
        return _bar_chart(
            counts,
            "Distribution of the number of contaminating sources per target",
            "Number of contaminants",
            y_label="Number of Stars",
            legend=[("Targets", "#4477AA")],
        )
    if kind == "flux":
        values = [_selected_flux(row) for row in rows]
        return _histogram(values, "Selected flux fraction", "Flux fraction (%)", y_label="Number of targets", legend=[("Targets", "#4477AA")])
    if kind == "separations":
        values = [_number(contaminant.get("sep_arcsec")) for contaminant in iter_contaminants(rows)]
        return _separation_histogram(values, "Distribution of angular separations", "Separation (arcsec)", "Number of contaminants")
    if kind == "flux-vs-separation":
        points = [(point["separation_arcsec"], point["flux_ratio_percent"]) for point in iter_contaminant_points(rows)]
        return _scatter(points, "Contaminant flux ratio vs separation", "Separation (arcsec)", "Contaminant flux / target flux (%)", legend=[("Contaminants", "#4477AA")])
    if kind == "contamination-vs-magnitude":
        points = [(_number(row.get("phot_g_mean_mag")), _selected_flux(row)) for row in rows if row.get("phot_g_mean_mag") is not None]
        return _scatter(points, "Target contamination vs magnitude", "Target magnitude", "Selected flux fraction (%)", legend=[("Targets", "#4477AA")])
    if kind == "sky-map":
        return _sky_map(rows)
    raise ValueError(f"Unsupported plot kind: {kind}")


def write_plot(rows: list[dict[str, Any]], kind: str, output_path: str | Path) -> str:
    """Write one SVG plot."""
    if kind not in PLOT_KINDS:
        raise ValueError(f"Plot kind must be one of: {', '.join(PLOT_KINDS)}")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(build_svg_plot(rows, kind), encoding="utf-8")
    return str(destination)


def write_matplotlib_plot(rows: list[dict[str, Any]], kind: str, output_path: str | Path) -> str:
    """Write a richer plot with matplotlib when the optional dependency exists."""
    if kind not in PLOT_KINDS:
        raise ValueError(f"Plot kind must be one of: {', '.join(PLOT_KINDS)}")
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise ImportError("Matplotlib plotting requires the optional matplotlib package.") from error

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4.8), constrained_layout=True)
    if kind == "contaminant-counts":
        count_values = [_int_number(row.get("num_contaminants", 0)) for row in rows]
        maximum = max(count_values, default=0)
        ax.hist(count_values, bins=range(0, maximum + 2), color="#4477AA", label='targets')
        if (any(value > 0 for value in count_values)):
            ax.set_yscale("log")
        ax.set_xlabel("Number of contaminants")
        ax.set_ylabel("Number of Stars")
        ax.set_title("Distribution of the number of contaminating sources per target")
        ax.legend()
    elif kind == "flux":
        flux_values = [_selected_flux(row) for row in rows]
        ax.hist(flux_values, bins=40, color="#66CCEE", label="targets")
        ax.set_xlabel("Selected flux fraction (%)")
        ax.set_ylabel("Number of targets")
        ax.set_title("Selected flux fraction")
        ax.legend()
    elif kind == "separations":
        separation_values = [value for value in (_number(contaminant.get("sep_arcsec")) for contaminant in iter_contaminants(rows)) if value is not None and value >= 0.0]
        maximum = int(max(separation_values, default=0))
        ax.hist(separation_values, bins=range(0, maximum + 2), color="#4477AA", label="contaminants")
        if (separation_values):
            ax.set_yscale("log")
        ax.set_xlabel("Separation (arcsec)")
        ax.set_ylabel("Number of contaminants")
        ax.set_title("Distribution of angular separations")
        ax.legend()
    elif kind == "flux-vs-separation":
        flux_points = list(iter_contaminant_points(rows))
        ax.scatter(
            [point["separation_arcsec"] for point in flux_points],
            [point["flux_ratio_percent"] for point in flux_points],
            s=8,
            c="#4477AA",
            alpha=0.65,
            linewidths=0,
            label="contaminants",
        )
        ax.set_xlabel("Separation (arcsec)")
        ax.set_ylabel("Contaminant flux / target flux (%)")
        ax.set_title("Contaminant flux ratio vs separation")
        ax.legend()
    elif kind == "contamination-vs-magnitude":
        magnitude_points = [(_number(row.get("phot_g_mean_mag")), _selected_flux(row)) for row in rows if row.get("phot_g_mean_mag") is not None]
        ax.scatter([point[0] for point in magnitude_points], [point[1] for point in magnitude_points], s=8, c="#4477AA", alpha=0.65, linewidths=0, label="targets")
        ax.set_xlabel("Target magnitude")
        ax.set_ylabel("Selected flux fraction (%)")
        ax.set_title("Target contamination vs magnitude")
        ax.legend()
    elif kind == "sky-map":
        # Single pass in catalogue order so no class is drawn on top of the others.
        ra_values = []
        dec_values = []
        point_colours = []
        for row in rows:
            ra = _number(row.get("ra"), None)  # type: ignore[arg-type]
            dec = _number(row.get("dec"), None)  # type: ignore[arg-type]
            if ra is None or dec is None:
                continue
            count = _int_number(row.get("num_contaminants", 0))
            index = 0 if count == 0 else (1 if count <= 3 else 2)
            ra_values.append(ra)
            dec_values.append(dec)
            point_colours.append(SKY_MAP_CLASSES[index][1])
        ax.scatter(ra_values, dec_values, s=2, c=point_colours, linewidths=0)
        ax.set_xlabel("RA [deg]")
        ax.set_ylabel("Dec [deg]")
        ax.set_title("Sky map of stellar contamination")
        legend_handles = [
            plt.Line2D([], [], marker="o", linestyle="", color=colour, markersize=6, label=label)
            for label, colour in SKY_MAP_CLASSES
        ]
        ax.legend(handles=legend_handles, loc="upper right")
    fig.savefig(destination)
    plt.close(fig)
    return str(destination)


def build_report(rows: list[dict[str, Any]], result_path: str | Path, output_format: str) -> str:
    """Build an HTML or Markdown report for one result table."""
    summary = summarize_results(rows, source_path=result_path)
    if output_format == "markdown":
        return (
            f"# {tr('PHOTO-CAT report')}\n\n"
            f"{tr('Source result')}: `{Path(result_path).resolve()}`\n\n"
            "```text\n"
            f"{summary_text(summary)}\n"
            "```\n"
        )

    if output_format == "pdf":
        raise ValueError("PDF reports must be written to a file.")
    if output_format != "html":
        raise ValueError(f"Report format must be one of: {', '.join(REPORT_FORMATS)}")

    plots = "\n".join(
        f"<section>{build_svg_plot(rows, kind)}</section>"
        for kind in ("contaminant-counts", "flux", "separations", "flux-vs-separation", "sky-map")
    )
    escaped_summary = html.escape(summary_text(summary))
    return (
        "<!doctype html>\n"
        f"<html lang=\"{get_language()}\"><meta charset=\"utf-8\"><title>{tr('PHOTO-CAT report')}</title>"
        "<style>body{font-family:sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;}"
        "pre{background:#f6f8fa;padding:1rem;overflow:auto;}section{margin:1.5rem 0;}</style>"
        f"<h1>{tr('PHOTO-CAT report')}</h1>"
        f"<p>{tr('Source result')}: <code>{html.escape(str(Path(result_path).resolve()))}</code></p>"
        f"<pre>{escaped_summary}</pre>"
        f"{plots}</html>\n"
    )


def _write_pdf_report(rows: list[dict[str, Any]], result_path: str | Path, output_path: str | Path) -> str:
    """Write a multi-page PDF containing the summary and diagnostic plots."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.image as mpimg
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_pdf import PdfPages
    except ImportError as error:
        raise ImportError("PDF report generation requires matplotlib.") from error

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize_results(rows, source_path=result_path)
    source_text = str(Path(result_path).resolve())
    with PdfPages(destination, metadata={"Title": "PHOTO-CAT report", "Subject": "Contamination screening summary"}) as pdf:
        figure = plt.figure(figsize=(8.27, 11.69), constrained_layout=True)
        figure.text(0.07, 0.95, tr("PHOTO-CAT report"), fontsize=18, weight="bold", va="top")
        figure.text(0.07, 0.91, f"{tr('Source result')}: {source_text}", fontsize=8, va="top", wrap=True)
        figure.text(0.07, 0.86, summary_text(summary), fontsize=10, family="monospace", va="top")
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)

        with tempfile.TemporaryDirectory(prefix="photo_cat_report_") as temporary_directory:
            temporary_path = Path(temporary_directory)
            for kind in ("contaminant-counts", "flux", "separations", "flux-vs-separation", "sky-map"):
                image_path = temporary_path / f"{kind}.png"
                write_matplotlib_plot(rows, kind, image_path)
                image = mpimg.imread(image_path)
                figure, axis = plt.subplots(figsize=(11.69, 8.27), constrained_layout=True)
                axis.imshow(image)
                axis.axis("off")
                pdf.savefig(figure, bbox_inches="tight")
                plt.close(figure)
    return str(destination)


def write_report(rows: list[dict[str, Any]], result_path: str | Path, output_path: str | Path, output_format: str) -> str:
    """Write an HTML or Markdown report."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "pdf":
        return _write_pdf_report(rows, result_path, destination)
    destination.write_text(build_report(rows, result_path, output_format), encoding="utf-8")
    return str(destination)


def flatten_result_row(row: dict[str, Any]) -> dict[str, Any]:
    """Flatten one target result for tabular export."""
    flattened = dict(row)
    contaminants = flattened.get("contaminants", [])
    flattened["contaminants_json"] = json.dumps(contaminants, ensure_ascii=False)
    flattened["contaminants"] = len(contaminants) if isinstance(contaminants, list) else 0
    outside_contaminants = flattened.get("outside_aperture_contaminants", [])
    flattened["outside_aperture_contaminants_json"] = json.dumps(outside_contaminants, ensure_ascii=False)
    flattened["outside_aperture_contaminants"] = (
        len(outside_contaminants) if isinstance(outside_contaminants, list) else 0
    )
    return flattened


def write_export(rows: list[dict[str, Any]], output_path: str | Path, output_format: str) -> str:
    """Export target-result rows as CSV or Parquet."""
    if output_format not in EXPORT_FORMATS:
        raise ValueError(f"Export format must be one of: {', '.join(EXPORT_FORMATS)}")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    flattened_rows = [flatten_result_row(row) for row in rows]

    if output_format == "csv":
        fieldnames = sorted({key for row in flattened_rows for key in row})
        with destination.open("x", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(flattened_rows)
        return str(destination)

    try:
        import pandas as pd
    except ImportError as error:
        raise ImportError("Parquet export requires pandas and pyarrow.") from error

    pd.DataFrame(flattened_rows).to_parquet(destination, index=False)
    return str(destination)
