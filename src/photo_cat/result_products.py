# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Summary, plotting, and report helpers for PHOTO-CAT query results."""

from __future__ import annotations

import csv
import html
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .index_manifest import atomic_write_json


SUMMARY_SCHEMA_VERSION = 1
PLOT_KINDS = (
    "contaminant-counts",
    "flux",
    "separations",
    "separations-normalized",
    "flux-vs-separation",
    "contamination-vs-magnitude",
    "sky-map",
)
REPORT_FORMATS = ("html", "markdown")
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
            "PHOTO-CAT result summary",
            f"Targets: {summary['target_count']}",
            f"With selected contaminants: {summary['targets_with_contaminants']}",
            f"Without selected contaminants: {summary['targets_without_contaminants']}",
            f"Selected contaminants: {summary['total_selected_contaminants']}",
            f"Neighbours in radius: {summary['total_neighbors_in_radius']}",
            f"Neighbours outside aperture: {summary['total_neighbors_outside_aperture']}",
            f"Selected flux % mean/median/max: {selected['mean']}/{selected['median']}/{selected['max']}",
            f"All-neighbour flux % mean/median/max: {all_neighbors['mean']}/{all_neighbors['median']}/{all_neighbors['max']}",
            f"Outside-aperture flux % mean/median/max: {outside['mean']}/{outside['median']}/{outside['max']}",
            f"Total weighted flux % mean/median/max: {total_weighted['mean']}/{total_weighted['median']}/{total_weighted['max']}",
            f"Contaminants per target mean/median/max: {counts['mean']}/{counts['median']}/{counts['max']}",
        ]
    if (transformed["count"] > 0):
        lines.append(
            "Transformed total weighted flux % mean/median/max: "
            f"{transformed['mean']}/{transformed['median']}/{transformed['max']}"
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


def _bar_chart(counts: Counter[int], title: str, x_label: str, width: int = 760, height: int = 420) -> str:
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
    for index, value in enumerate(values):
        bar_height = (counts[value] / max_count) * plot_height
        x = plot_left + index * bar_width
        y = plot_top + plot_height - bar_height
        body.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(bar_width - 2, 1):.2f}" height="{bar_height:.2f}" fill="#4477AA"/>')
        if len(values) <= 20:
            body.append(f'<text x="{x + bar_width / 2:.2f}" y="{plot_top + plot_height + 14}" text-anchor="middle" font-family="sans-serif" font-size="10">{value}</text>')
    body.append(f'<text x="14" y="{plot_top + 12}" font-family="sans-serif" font-size="11">max bin count: {max_count}</text>')
    return _svg_frame(width, height, title, "\n".join(body))


def _histogram(values: list[float], title: str, x_label: str, bins: int = 20) -> str:
    if not values:
        return _bar_chart(Counter(), title, x_label)
    low, high = min(values), max(values)
    if low == high:
        return _bar_chart(Counter({int(round(low)): len(values)}), title, x_label)
    step = (high - low) / bins
    counts: Counter[int] = Counter()
    for value in values:
        bucket = min(int((value - low) / step), bins - 1)
        counts[bucket] += 1
    labels = {bucket: f"{low + bucket * step:.1f}" for bucket in counts}
    svg = _bar_chart(counts, title, x_label)
    for bucket, label in labels.items():
        svg = svg.replace(f">{bucket}</text>", f">{html.escape(label)}</text>")
    return svg


def _bar_values(labels: list[str], heights: list[float], title: str, x_label: str, y_label: str, width: int = 760, height: int = 420) -> str:
    plot_left, plot_top, plot_width, plot_height = 80, 48, width - 125, height - 120
    max_height = max(heights) if heights else 1.0
    max_height = max_height if max_height > 0 else 1.0
    bar_width = max(1, plot_width / max(len(heights), 1))
    body = [
        f'<line x1="{plot_left}" y1="{plot_top + plot_height}" x2="{plot_left + plot_width}" y2="{plot_top + plot_height}" stroke="#333"/>',
        f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_top + plot_height}" stroke="#333"/>',
        f'<text x="{width / 2:.1f}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="12">{html.escape(x_label)}</text>',
        f'<text x="18" y="{plot_top + plot_height / 2:.1f}" transform="rotate(-90 18 {plot_top + plot_height / 2:.1f})" text-anchor="middle" font-family="sans-serif" font-size="12">{html.escape(y_label)}</text>',
    ]
    for index, value in enumerate(heights):
        bar_height = (value / max_height) * plot_height
        x = plot_left + index * bar_width
        y = plot_top + plot_height - bar_height
        body.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(bar_width - 2, 1):.2f}" height="{bar_height:.2f}" fill="#4477AA"/>')
        if len(labels) <= 20:
            body.append(f'<text x="{x + bar_width / 2:.2f}" y="{plot_top + plot_height + 14}" text-anchor="middle" font-family="sans-serif" font-size="9">{html.escape(labels[index])}</text>')
    return _svg_frame(width, height, title, "\n".join(body))


def _area_normalized_separation_histogram(rows: list[dict[str, Any]], bins: int = 20) -> str:
    values = [_number(contaminant.get("sep_arcsec")) for contaminant in iter_contaminants(rows)]
    if (not values):
        return _bar_values([], [], "Area-normalized contaminant separations", "separation (arcsec)", "contaminants / arcsec²")
    high = max(values)
    if (high <= 0.0):
        high = 1.0
    step = high / bins
    counts = [0] * bins
    for value in values:
        bucket = min(int(value / step), bins - 1)
        counts[bucket] += 1
    densities: list[float] = []
    labels: list[str] = []
    for index, count in enumerate(counts):
        inner = index * step
        outer = (index + 1) * step
        annular_area = math.pi * (outer**2 - inner**2)
        densities.append(count / annular_area if annular_area > 0 else 0.0)
        labels.append(f"{inner:.0f}-{outer:.0f}")
    return _bar_values(labels, densities, "Area-normalized contaminant separations", "separation (arcsec)", "contaminants / arcsec²")


def _scatter(points: list[tuple[float, float]], title: str, x_label: str, y_label: str, width: int = 760, height: int = 420) -> str:
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
    return _svg_frame(width, height, title, "\n".join(body))


def _severity_style(count: int) -> tuple[str, float, float]:
    """Map contaminant count to a colourblind-safe colour plus a redundant marker size.

    Encoding severity by marker size as well as hue keeps the three levels
    distinguishable without relying on colour vision (Paul Tol bright palette).
    Returns (hex_colour, svg_radius, matplotlib_area).
    """
    if (count == 0):
        return "#228833", 2.0, 6.0
    if (count <= 3):
        return "#CCBB44", 3.2, 16.0
    return "#EE6677", 4.6, 34.0


def _sky_map(rows: list[dict[str, Any]], width: int = 760, height: int = 420) -> str:
    plot_left, plot_top, plot_width, plot_height = 60, 48, width - 100, height - 100
    body = [
        f'<rect x="{plot_left}" y="{plot_top}" width="{plot_width}" height="{plot_height}" fill="#f7f7f7" stroke="#333"/>',
        f'<text x="{width / 2:.1f}" y="{height - 18}" text-anchor="middle" font-family="sans-serif" font-size="12">RA/Dec target positions</text>',
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
        body.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.1f}" fill="{color}" fill-opacity="0.75"/>')
    body.append(f'<text x="{plot_left}" y="{plot_top - 8}" font-family="sans-serif" font-size="11">marker size &amp; colour: small=0, medium=1–3, large=&gt;3 contaminants</text>')
    return _svg_frame(width, height, "PHOTO-CAT sky map", "\n".join(body))


def build_svg_plot(rows: list[dict[str, Any]], kind: str) -> str:
    """Build a dependency-free SVG plot for one result table."""
    if kind == "contaminant-counts":
        counts = Counter(_int_number(row.get("num_contaminants", 0)) for row in rows)
        return _bar_chart(counts, "Contaminants per target", "selected contaminants")
    if kind == "flux":
        values = [_selected_flux(row) for row in rows]
        return _histogram(values, "Selected flux fraction", "flux fraction (%)")
    if kind == "separations":
        values = [_number(contaminant.get("sep_arcsec")) for contaminant in iter_contaminants(rows)]
        return _histogram(values, "Contaminant separations", "separation (arcsec)")
    if kind == "separations-normalized":
        return _area_normalized_separation_histogram(rows)
    if kind == "flux-vs-separation":
        points = [(point["separation_arcsec"], point["flux_ratio_percent"]) for point in iter_contaminant_points(rows)]
        return _scatter(points, "Contaminant flux ratio vs separation", "separation (arcsec)", "contaminant flux / target flux (%)")
    if kind == "contamination-vs-magnitude":
        points = [(_number(row.get("phot_g_mean_mag")), _selected_flux(row)) for row in rows if row.get("phot_g_mean_mag") is not None]
        return _scatter(points, "Target contamination vs magnitude", "target magnitude", "selected flux fraction (%)")
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
        values = [_int_number(row.get("num_contaminants", 0)) for row in rows]
        ax.hist(values, bins=min(max(len(set(values)), 1), 40), color="#4477AA")
        ax.set_xlabel("selected contaminants")
        ax.set_ylabel("targets")
        ax.set_title("Contaminants per target")
    elif kind == "flux":
        values = [_selected_flux(row) for row in rows]
        ax.hist(values, bins=40, color="#66CCEE")
        ax.set_xlabel("selected flux fraction (%)")
        ax.set_ylabel("targets")
        ax.set_title("Selected flux fraction")
    elif kind == "separations":
        values = [_number(contaminant.get("sep_arcsec")) for contaminant in iter_contaminants(rows)]
        ax.hist(values, bins=40, color="#228833")
        ax.set_xlabel("separation (arcsec)")
        ax.set_ylabel("selected contaminants")
        ax.set_title("Contaminant separations")
    elif kind == "separations-normalized":
        values = [_number(contaminant.get("sep_arcsec")) for contaminant in iter_contaminants(rows)]
        if values:
            counts, bins, patches = ax.hist(values, bins=40, color="#4477AA")
            for count, patch, inner, outer in zip(counts, patches, bins[:-1], bins[1:]):
                area = math.pi * (outer**2 - inner**2)
                patch.set_height(count / area if area > 0 else 0.0)
        else:
            ax.hist(values, bins=40, color="#4477AA")
        ax.set_xlabel("separation (arcsec)")
        ax.set_ylabel("contaminants / arcsec²")
        ax.set_title("Area-normalized contaminant separations")
    elif kind == "flux-vs-separation":
        points = list(iter_contaminant_points(rows))
        ax.scatter(
            [point["separation_arcsec"] for point in points],
            [point["flux_ratio_percent"] for point in points],
            s=8,
            c="#4477AA",
            alpha=0.65,
            linewidths=0,
        )
        ax.set_xlabel("separation (arcsec)")
        ax.set_ylabel("contaminant flux / target flux (%)")
        ax.set_title("Contaminant flux ratio vs separation")
    elif kind == "contamination-vs-magnitude":
        points = [(_number(row.get("phot_g_mean_mag")), _selected_flux(row)) for row in rows if row.get("phot_g_mean_mag") is not None]
        ax.scatter([point[0] for point in points], [point[1] for point in points], s=8, c="#4477AA", alpha=0.65, linewidths=0)
        ax.set_xlabel("target magnitude")
        ax.set_ylabel("selected flux fraction (%)")
        ax.set_title("Target contamination vs magnitude")
    elif kind == "sky-map":
        ra_values = []
        dec_values = []
        colours = []
        sizes = []
        for row in rows:
            ra = _number(row.get("ra"), None)  # type: ignore[arg-type]
            dec = _number(row.get("dec"), None)  # type: ignore[arg-type]
            if ra is None or dec is None:
                continue
            count = _int_number(row.get("num_contaminants", 0))
            colour, _, size = _severity_style(count)
            ra_values.append(ra)
            dec_values.append(dec)
            colours.append(colour)
            sizes.append(size)
        ax.scatter(ra_values, dec_values, s=sizes, c=colours, alpha=0.75, linewidths=0)
        ax.set_xlabel("RA (deg)")
        ax.set_ylabel("Dec (deg)")
        ax.set_title("PHOTO-CAT sky map")
    fig.savefig(destination)
    plt.close(fig)
    return str(destination)


def build_report(rows: list[dict[str, Any]], result_path: str | Path, output_format: str) -> str:
    """Build an HTML or Markdown report for one result table."""
    summary = summarize_results(rows, source_path=result_path)
    if output_format == "markdown":
        return (
            "# PHOTO-CAT report\n\n"
            f"Source result: `{Path(result_path).resolve()}`\n\n"
            "```text\n"
            f"{summary_text(summary)}\n"
            "```\n"
        )

    if output_format != "html":
        raise ValueError(f"Report format must be one of: {', '.join(REPORT_FORMATS)}")

    plots = "\n".join(
        f"<section>{build_svg_plot(rows, kind)}</section>"
        for kind in ("contaminant-counts", "flux", "separations-normalized", "flux-vs-separation", "sky-map")
    )
    escaped_summary = html.escape(summary_text(summary))
    return (
        "<!doctype html>\n"
        "<html lang=\"en\"><meta charset=\"utf-8\"><title>PHOTO-CAT report</title>"
        "<style>body{font-family:sans-serif;max-width:980px;margin:2rem auto;padding:0 1rem;}"
        "pre{background:#f6f8fa;padding:1rem;overflow:auto;}section{margin:1.5rem 0;}</style>"
        "<h1>PHOTO-CAT report</h1>"
        f"<p>Source result: <code>{html.escape(str(Path(result_path).resolve()))}</code></p>"
        f"<pre>{escaped_summary}</pre>"
        f"{plots}</html>\n"
    )


def write_report(rows: list[dict[str, Any]], result_path: str | Path, output_path: str | Path, output_format: str) -> str:
    """Write an HTML or Markdown report."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
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
