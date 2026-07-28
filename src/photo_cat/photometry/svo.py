# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Fetch filter transmission curves from the SVO Filter Profile Service.

The built-in library ships a few official curves; this module lets the user pull
any other filter from the SVO Filter Profile Service
(http://svo2.cab.inta-csic.es/theory/fps/) into that library, one at a time, and
use it immediately. Filters are organised by facility, so listing is scoped to a
facility, which is also how SVO itself organises them.

Only the Python standard library is used, so importing PHOTO-CAT never requires a
network. Network calls happen only when these functions are called, always with a
timeout, and raise a clear ``SvoError`` on failure.
"""

from __future__ import annotations

import datetime
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree

from .filters import load_filter
from .library import normalized_band_key

SVO_FPS_BASE = "http://svo2.cab.inta-csic.es/theory/fps"

# Each facility link in the SVO index carries a hover tooltip describing it. The name
# is repeated in bold at the start of that tooltip, before the description proper.
_FACILITY_RE = re.compile(r"gname=([^&\"']+)[^>]*onMouseOver=\"Tip\('(.*?)'\)\"", re.S)


@dataclass(frozen=True)
class SvoFacility:
    """One facility from the SVO index, with the site's own one-line description."""

    name: str
    description: str


def list_facilities(timeout: float = 30.0) -> list[SvoFacility]:
    """Return every facility SVO groups filters under, with its site description.

    The list, its order, and the descriptions are read live from the SVO index, so
    nothing is hand-maintained in the tool; a facility SVO adds appears automatically.
    The description (e.g. ``Gaia mission.`` vs ``Miscellaneous...``) lets the picker
    show what each entry is, so a catalogue grouping is not mistaken for a mission.
    Returns an empty list when the service is unreachable (the picker is editable, so
    a known facility can still be typed).
    """
    try:
        body = _http_get(f"{SVO_FPS_BASE}/", timeout).decode("utf-8", errors="replace")
    except SvoError:
        return []

    facilities: list[SvoFacility] = []
    seen: set[str] = set()
    for name, tooltip in _FACILITY_RE.findall(body):
        if (not name or name in seen):
            continue
        seen.add(name)
        description = re.sub(r"<[^>]+>", " ", unescape(tooltip))
        description = " ".join(description.split())
        if (description.lower().startswith(name.lower())):
            description = description[len(name):].strip()
        facilities.append(SvoFacility(name, description))
    return facilities


class SvoError(RuntimeError):
    """Raised when an SVO request fails or returns something unusable."""


@dataclass(frozen=True)
class SvoFilter:
    """One filter entry from an SVO facility listing."""

    filter_id: str
    band: str
    description: str
    wavelength_mean_nm: float | None

    def label(self) -> str:
        """Return a human-readable dropdown label."""
        parts = [self.filter_id]
        if (self.wavelength_mean_nm is not None):
            parts.append(f"~{self.wavelength_mean_nm:.0f} nm")
        if (self.description):
            parts.append(self.description)
        return "  -  ".join(parts)


def _http_get(url: str, timeout: float) -> bytes:
    """Return the raw body of an HTTP GET, or raise a clear SvoError."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (fixed SVO host)
            return response.read()
    except urllib.error.HTTPError as error:
        raise SvoError(f"SVO returned HTTP {error.code} for {url}") from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise SvoError(f"Could not reach the SVO service: {error}") from error


def _local_tag(tag: str) -> str:
    """Return an XML tag without its namespace."""
    return tag.rsplit("}", 1)[-1]


def list_filters(facility: str, timeout: float = 30.0) -> list[SvoFilter]:
    """Return the filters SVO lists for one facility.

    The metadata API keys on the ``Facility`` field, which differs from the browse
    grouping name for many missions (e.g. DENIS, Geneva, Beijing1), so the API
    alone misses them. The metadata query is tried first for its richer labels
    (description and mean wavelength); when it returns nothing, the browse index
    is parsed instead, which lists filter IDs for every grouping the site shows.
    """
    facility = facility.strip()
    if (facility == ""):
        raise SvoError("Choose a facility before listing filters.")

    filters = _list_via_metadata(facility, timeout)
    if (not filters):
        filters = _list_via_browse(facility, timeout)
    if (not filters):
        raise SvoError(f"SVO lists no downloadable filters for '{facility}'.")
    return filters


def _list_via_metadata(facility: str, timeout: float) -> list[SvoFilter]:
    """List filters through the VOTable metadata API, or return [] if it serves none.

    Reads the ``filterID``, ``Description`` and ``WavelengthMean`` columns by name so
    column-order changes do not break it.
    """
    body = _http_get(f"{SVO_FPS_BASE}/fps.php?Facility={quote(facility)}", timeout)
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError:
        return []

    for info in root.iter():
        if (_local_tag(info.tag) == "INFO" and info.get("name") == "QUERY_STATUS"
                and (info.get("value") or "").upper() == "ERROR"):
            return []

    fields: list[str] = []
    rows: list[list[str]] = []
    for element in root.iter():
        tag = _local_tag(element.tag)
        if (tag == "FIELD"):
            fields.append(element.get("name", ""))
        elif (tag == "TR"):
            rows.append([(cell.text or "").strip() for cell in element if _local_tag(cell.tag) == "TD"])

    if ("filterID" not in fields):
        return []
    id_index = fields.index("filterID")
    description_index = fields.index("Description") if ("Description" in fields) else None
    mean_index = fields.index("WavelengthMean") if ("WavelengthMean" in fields) else None

    filters: list[SvoFilter] = []
    for row in rows:
        if (id_index >= len(row) or not row[id_index]):
            continue
        filter_id = row[id_index]
        description = row[description_index] if (description_index is not None and description_index < len(row)) else ""
        wavelength_mean_nm = None
        if (mean_index is not None and mean_index < len(row) and row[mean_index]):
            try:
                wavelength_mean_nm = float(row[mean_index]) / 10.0  # Angstrom -> nm
            except ValueError:
                wavelength_mean_nm = None
        filters.append(
            SvoFilter(filter_id, filter_id.split("/", 1)[-1], " ".join(description.split()), wavelength_mean_nm)
        )
    return filters


# A browse page can split a facility's filters across instrument sub-pages linked
# by ``gname2``; the crawl follows them. The cap bounds a facility to a sane number
# of sub-pages so a malformed or looping index can never hang the request.
_BROWSE_MAX_PAGES = 300


def _list_via_browse(facility: str, timeout: float) -> list[SvoFilter]:
    """List filters by crawling the browse index, following instrument sub-groups.

    The metadata API misses facilities whose ``Facility`` field differs from the
    browse name, and a facility's filters can be nested under ``gname2`` sub-pages.
    This crawls the top page and each sub-page, extracting ids anchored to the
    download link (``id=<facility>/<band>``). Only ids are available here, not
    descriptions or wavelengths.
    """
    id_pattern = r"id=(" + re.escape(facility) + r"/[A-Za-z0-9][A-Za-z0-9._+-]*\.[A-Za-z0-9._+-]+)"
    seen_ids: set[str] = set()
    filters: list[SvoFilter] = []
    visited: set[str] = set()
    pending: list[str | None] = [None]  # None is the top page; strings are gname2 values

    while (pending and len(visited) < _BROWSE_MAX_PAGES):
        sub = pending.pop()
        url = f"{SVO_FPS_BASE}/index.php?mode=browse&gname={quote(facility)}"
        if (sub is not None):
            url += f"&gname2={quote(sub)}"
        if (url in visited):
            continue
        visited.add(url)
        try:
            body = _http_get(url, timeout).decode("utf-8", errors="replace")
        except SvoError:
            continue
        for filter_id in re.findall(id_pattern, body):
            if (filter_id not in seen_ids):
                seen_ids.add(filter_id)
                filters.append(SvoFilter(filter_id, filter_id.split("/", 1)[-1], "", None))
        for found in re.findall(r"gname2=([A-Za-z0-9._+-]+)", body):
            candidate_url = f"{SVO_FPS_BASE}/index.php?mode=browse&gname={quote(facility)}&gname2={quote(found)}"
            if (candidate_url not in visited):
                pending.append(found)
    return filters


def _filter_id_parts(filter_id: str) -> tuple[str, str]:
    """Split an SVO filter id into a facility folder and a band file stem."""
    facility, _, remainder = filter_id.partition("/")
    facility = facility or "SVO"
    band = remainder or filter_id
    # "CHEOPS.band" -> "band", "GAIA3.G" -> "G", "TESS.Red" -> "Red".
    if ("." in band):
        band = band.rsplit(".", 1)[-1]
    return facility, (band or "band")


def download_filter(filter_id: str, filters_root: str | Path, timeout: float = 30.0) -> Path:
    """Download one SVO filter into the library and return its saved path.

    The curve is written in PHOTO-CAT's filter format under
    ``<filters_root>/<Facility>/<band>.dat``, so it is immediately discoverable and
    selectable as an output band.
    """
    if (not filter_id.strip()):
        raise SvoError("Choose a filter to download.")
    url = f"{SVO_FPS_BASE}/getdata.php?format=ascii&id={quote(filter_id.strip())}"
    body = _http_get(url, timeout).decode("utf-8", errors="replace")

    data_rows = [line for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    parsed: list[str] = []
    for line in data_rows:
        parts = re.split(r"[\s,]+", line.strip())
        if (len(parts) >= 2):
            try:
                float(parts[0])
                float(parts[1])
            except ValueError:
                continue
            parsed.append(f"{parts[0]} {parts[1]}")
    if (len(parsed) < 2):
        raise SvoError(f"SVO returned no usable transmission data for '{filter_id}'.")

    facility, band = _filter_id_parts(filter_id)
    destination = Path(filters_root) / facility / f"{band}.dat"
    destination.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# {filter_id} passband\n"
        f"# Source: SVO Filter Profile Service, filter id {filter_id}\n"
        f"# Retrieved: {datetime.date.today().isoformat()} via {SVO_FPS_BASE}/\n"
        f"# provenance: official\n# unit: angstrom\n# transmission: fraction\n"
    )
    destination.write_text(header + "\n".join(parsed) + "\n", encoding="utf-8")

    # Validate what we just wrote so a corrupt download fails now, not at query time.
    try:
        load_filter(destination)
    except ValueError as error:
        destination.unlink(missing_ok=True)
        raise SvoError(f"Downloaded filter '{filter_id}' could not be parsed: {error}") from error
    return destination


def band_key_for_filter_id(filter_id: str) -> str:
    """Return the output-band key a downloaded filter will be selectable under."""
    facility, band = _filter_id_parts(filter_id)
    return normalized_band_key(f"{facility}_{band}")
