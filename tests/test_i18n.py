# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""English/Italian interface and beginner-guidance regression tests."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from photo_cat import cli
from photo_cat.i18n import (
    ITALIAN,
    LANGUAGE_ENVIRONMENT,
    TOOLTIPS_EN,
    TOOLTIPS_IT,
    initialize_language,
    set_language,
    tooltip_for,
    tr,
)
from photo_cat.publication_plots import generate_publication_plots
from photo_cat.result_products import summarize_results, summary_text


@pytest.fixture(autouse=True)
def restore_english(monkeypatch: pytest.MonkeyPatch):
    """Keep process-wide localization isolated from the rest of the suite."""
    monkeypatch.delenv(LANGUAGE_ENVIRONMENT, raising=False)
    set_language("en")
    yield
    set_language("en")


@pytest.mark.unit
def test_language_precedence_and_config_selection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit language wins, while a config can select Italian when no override exists."""
    config = tmp_path / "config.yaml"
    config.write_text("interface:\n  language: it\n", encoding="utf-8")

    monkeypatch.delenv(LANGUAGE_ENVIRONMENT, raising=False)
    assert initialize_language(config) == "it"
    assert tr("Language") == "Lingua"
    assert initialize_language(config, "en") == "en"
    assert tr("Language") == "Language"


@pytest.mark.regression
def test_cli_help_and_expected_errors_are_italian(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The public CLI translates both guidance and expected user-error boundaries."""
    with pytest.raises(SystemExit) as help_exit:
        cli.main(["--language", "it", "--help"])
    assert help_exit.value.code == 0
    help_text = capsys.readouterr().out
    assert "lingua usata per aiuto, messaggi, errori" in help_text
    assert "Strumenti PHOTO-CAT per valutare il rischio" in help_text

    assert cli.main(["--language", "it", "build-index", "--config", str(tmp_path / "assente.yaml")]) == 1
    error_text = capsys.readouterr().err
    assert error_text.startswith("ERRORE:")
    assert "non è stato trovato" in error_text

    with pytest.raises(SystemExit) as parse_exit:
        cli.main(["--language", "it", "plot", "result.json", "--backend", "inesistente"])
    assert parse_exit.value.code == 2
    parse_error = capsys.readouterr().err
    assert "ERRORE:" in parse_error
    assert "scelta non valida" in parse_error


@pytest.mark.unit
def test_summary_text_follows_interface_language() -> None:
    """Human-readable summaries follow the interface language without changing schemas."""
    summary = summarize_results([{"source_id": "1", "num_contaminants": 0, "contaminants": []}])
    set_language("it")

    rendered = summary_text(summary)

    assert rendered.startswith("Riepilogo dei risultati PHOTO-CAT")
    assert "Senza contaminanti selezionati: 1" in rendered


@pytest.mark.unit
def test_beginner_tooltips_cover_both_languages_and_have_fallbacks() -> None:
    """Critical astronomy fields have bespoke bilingual help and unknown controls remain explained."""
    assert set(TOOLTIPS_EN) == set(TOOLTIPS_IT)
    for key in ("Catalog RA column", "Delta magnitude", "Gaussian FWHM, arcsec", "Metric"):
        set_language("en")
        english = tooltip_for(key)
        set_language("it")
        italian = tooltip_for(key)
        assert english
        assert italian
        assert english != italian

    assert "impostazione sconosciuta" in tooltip_for("impostazione sconosciuta")


@pytest.mark.unit
def test_every_static_gui_label_has_an_italian_catalog_entry() -> None:
    """New static GUI text must not silently bypass the complete Italian catalogue."""
    source = Path("src/photo_cat/configure_gui.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    labels: set[str] = set()
    option_labels: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if (
                    keyword.arg in {"text", "title"}
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                    and keyword.value.value
                ):
                    labels.add(keyword.value.value)
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr in {"showerror", "showwarning", "showinfo", "askyesno", "askokcancel"}
            ):
                    for argument in node.args[:2]:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str) and argument.value:
                            labels.update(line for line in argument.value.splitlines() if line)
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value in {"title", "description", "label", "run_label"}
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                    and value.value
                ):
                    labels.add(value.value)
                    if key.value != "description":
                        option_labels.add(value.value)

    assert labels
    assert labels <= set(ITALIAN)
    assert option_labels <= set(TOOLTIPS_EN)
    assert option_labels <= set(TOOLTIPS_IT)

    set_language("it")
    assert tr("Save config.yaml") == "Salva config.yaml"
    assert tr("Save + run pipeline") == "Salva e avvia la pipeline"


@pytest.mark.regression
def test_scientific_plot_labels_remain_english_in_italian_mode(tmp_path: Path) -> None:
    """Publication products use stable English labels regardless of the interface locale."""
    result_path = tmp_path / "results.json"
    result_path.write_text(
        json.dumps([
            {
                "source_id": "1",
                "ra": 10.0,
                "dec": 20.0,
                "num_contaminants": 1,
                "contaminants": [{"source_id": "2", "sep_arcsec": 3.0}],
            }
        ]),
        encoding="utf-8",
    )
    set_language("it")

    payload = generate_publication_plots(
        result_path,
        tmp_path / "plots",
        aperture_arcsec=47.0,
        output_format="svg",
        dpi=72,
    )
    count_svg = Path(payload["plots"]["contaminant_count_distribution"]["path"]).read_text(encoding="utf-8")
    sky_svg = Path(payload["plots"]["contamination_sky_map"]["path"]).read_text(encoding="utf-8")

    assert "Number of contaminants" in count_svg
    assert "Number of Stars" in count_svg
    assert "0 contaminants" in sky_svg
    assert "0 contaminanti" not in sky_svg
