# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Unit tests for the SVO filter downloader (network mocked)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from photo_cat.photometry import svo
from photo_cat.photometry.filters import load_filter

_VOTABLE = """<?xml version="1.0"?>
<VOTABLE version="1.1" xmlns="http://www.ivoa.net/xml/VOTable/v1.1">
 <RESOURCE><TABLE>
  <FIELD name="FilterProfileService"/>
  <FIELD name="filterID"/>
  <FIELD name="Description"/>
  <FIELD name="WavelengthMean"/>
  <DATA><TABLEDATA>
   <TR><TD>ivo://svo/fps</TD><TD>TESS/TESS.Red</TD><TD>TESS   red band</TD><TD>7865.0</TD></TR>
   <TR><TD>ivo://svo/fps</TD><TD>TESS/TESS.Other</TD><TD>Another</TD><TD>6000.0</TD></TR>
  </TABLEDATA></DATA>
 </TABLE></RESOURCE>
</VOTABLE>"""

_ERROR_VOTABLE = """<?xml version="1.0"?>
<VOTABLE version="1.1" xmlns="http://www.ivoa.net/xml/VOTable/v1.1">
 <INFO name="QUERY_STATUS" value="ERROR"><DESCRIPTION>No filter found</DESCRIPTION></INFO>
</VOTABLE>"""

_ASCII = "# TESS\n5670 0.0\n6000 0.5\n7865 1.0\n9000 0.5\n11270 0.0\n"


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _patch_urlopen(monkeypatch, payload: bytes):
    monkeypatch.setattr(svo.urllib.request, "urlopen", lambda url, timeout=0: _FakeResponse(payload))


@pytest.mark.unit
def test_list_filters_parses_filter_ids_by_column_name(monkeypatch) -> None:
    """Filter IDs are read from the named column, tolerant of column order."""
    _patch_urlopen(monkeypatch, _VOTABLE.encode())
    filters = svo.list_filters("TESS")
    assert [f.filter_id for f in filters] == ["TESS/TESS.Red", "TESS/TESS.Other"]
    assert filters[0].wavelength_mean_nm == pytest.approx(786.5)  # 7865 A -> nm
    assert "TESS/TESS.Red" in filters[0].label()


@pytest.mark.unit
def test_list_filters_raises_when_neither_source_serves_filters(monkeypatch) -> None:
    """When the metadata API errors and the browse page is empty, fail clearly."""
    _patch_urlopen(monkeypatch, _ERROR_VOTABLE.encode())
    with pytest.raises(svo.SvoError, match="no downloadable filters"):
        svo.list_filters("Generic")


@pytest.mark.unit
def test_list_filters_falls_back_to_browse_when_metadata_errors(monkeypatch) -> None:
    """Missions whose Facility field differs from the browse name are found via browse."""
    browse_html = (
        '<a href="getdata.php?id=DENIS/DENIS.I">I</a>'
        '<a href="getdata.php?id=DENIS/DENIS.J">J</a>'
        '<a href="getdata.php?id=DENIS/DENIS.Ks">Ks</a>'
        'stray token DENIS/DENIS.a should be ignored'
    )

    def dispatch(url, timeout=0):
        payload = browse_html if ("mode=browse" in url) else _ERROR_VOTABLE
        return _FakeResponse(payload.encode())

    monkeypatch.setattr(svo.urllib.request, "urlopen", dispatch)
    filters = svo.list_filters("DENIS")
    assert [f.filter_id for f in filters] == ["DENIS/DENIS.I", "DENIS/DENIS.J", "DENIS/DENIS.Ks"]


@pytest.mark.unit
def test_browse_fallback_follows_instrument_subgroups(monkeypatch) -> None:
    """Filters nested under gname2 sub-pages are collected by the browse crawl."""
    top = 'top page <a href="index.php?mode=browse&gname=Generic&gname2=Johnson">Johnson</a>' \
          '<a href="index.php?mode=browse&gname=Generic&gname2=Bessell">Bessell</a>'
    johnson = '<a href="getdata.php?id=Generic/Johnson.V">V</a><a href="getdata.php?id=Generic/Johnson.B">B</a>'
    bessell = '<a href="getdata.php?id=Generic/Bessell.U">U</a>'

    def dispatch(url, timeout=0):
        if ("mode=browse" not in url):
            payload = _ERROR_VOTABLE
        elif ("gname2=Johnson" in url):
            payload = johnson
        elif ("gname2=Bessell" in url):
            payload = bessell
        else:
            payload = top
        return _FakeResponse(payload.encode())

    monkeypatch.setattr(svo.urllib.request, "urlopen", dispatch)
    ids = {f.filter_id for f in svo.list_filters("Generic")}
    assert ids == {"Generic/Johnson.V", "Generic/Johnson.B", "Generic/Bessell.U"}


@pytest.mark.unit
def test_list_facilities_parses_names_and_descriptions_from_the_index(monkeypatch) -> None:
    """Live discovery reads each facility's name and its site description, in order."""
    index = (
        '<a href="index.php?mode=browse&gname=GAIA&asttype="'
        ' onMouseOver="Tip(\'&lt;b&gt;GAIA&lt;/b&gt;&lt;br&gt;Gaia mission.\')">GAIA</a>'
        '<a href="index.php?mode=browse&gname=Misc&asttype="'
        ' onMouseOver="Tip(\'&lt;b&gt;Misc&lt;/b&gt;&lt;br&gt;Miscellaneous. Filters not in a category.\')">Misc</a>'
    )
    _patch_urlopen(monkeypatch, index.encode())
    facilities = svo.list_facilities()
    assert [f.name for f in facilities] == ["GAIA", "Misc"]
    assert facilities[0].description == "Gaia mission."
    # The description is what distinguishes a grouping from a mission.
    assert "Miscellaneous" in facilities[1].description


@pytest.mark.unit
def test_facility_display_shows_name_and_description() -> None:
    """The picker label pairs the name with the site description, truncated if long."""
    from photo_cat.configure_gui import svo_facility_display

    assert svo_facility_display(svo.SvoFacility("GAIA", "Gaia mission.")) == "GAIA  —  Gaia mission."
    assert svo_facility_display(svo.SvoFacility("X", "")) == "X"
    long = svo_facility_display(svo.SvoFacility("Y", "d" * 200))
    assert long.startswith("Y  —  ") and long.endswith("…") and len(long) < 90


@pytest.mark.unit
def test_list_facilities_is_empty_when_offline(monkeypatch) -> None:
    """A network failure yields an empty list (the editable picker still works)."""
    def boom(url, timeout=0):
        raise svo.urllib.error.URLError("offline")

    monkeypatch.setattr(svo.urllib.request, "urlopen", boom)
    assert svo.list_facilities() == []


@pytest.mark.unit
def test_download_filter_writes_a_loadable_curve(monkeypatch, tmp_path: Path) -> None:
    """A downloaded filter is written in the library format and parses back."""
    _patch_urlopen(monkeypatch, _ASCII.encode())
    path = svo.download_filter("TESS/TESS.Red", tmp_path)
    assert path == tmp_path / "TESS" / "Red.dat"
    curve = load_filter(path)
    assert curve.provenance == "official"
    assert curve.wavelength_nm[0] == pytest.approx(567.0)  # 5670 A -> nm
    assert curve.throughput.max() == pytest.approx(1.0)


@pytest.mark.unit
def test_download_filter_rejects_a_response_without_data(monkeypatch, tmp_path: Path) -> None:
    """A response with no numeric rows fails clearly and leaves no file behind."""
    _patch_urlopen(monkeypatch, b"# only a comment\n")
    with pytest.raises(svo.SvoError, match="no usable transmission data"):
        svo.download_filter("TESS/TESS.Red", tmp_path)
    assert not (tmp_path / "TESS" / "Red.dat").exists()


@pytest.mark.unit
@pytest.mark.parametrize(
    ("filter_id", "band_key"),
    [
        ("GAIA/GAIA3.G", "gaia_g"),
        ("TESS/TESS.Red", "tess_red"),
        ("CHEOPS/CHEOPS.band", "cheops_band"),
        ("Kepler/Kepler.K", "kepler_k"),
    ],
)
def test_band_key_for_filter_id(filter_id: str, band_key: str) -> None:
    """The saved band key is derived predictably from the SVO filter id."""
    assert svo.band_key_for_filter_id(filter_id) == band_key
