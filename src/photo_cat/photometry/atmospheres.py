# SPDX-FileCopyrightText: 2026 PHOTO-CAT contributors
# SPDX-License-Identifier: GPL-3.0-only
"""Model-atmosphere grids fetched a node at a time and cached, resampled, on disk.

A model atmosphere gives a spectrum from (Teff, log g, [M/H]), which the conversion
then reddens, normalises on the catalogue band and integrates through the requested
filter. Shipping those grids is not possible: at the spacing the physics needs --
measured on real spectra at about 0.5 dex in log g and [M/H] and 100-200 K in Teff
for one per cent interpolation error -- a useful grid is thousands of nodes, and one
BT-Settl spectrum is roughly 18 MB.

So nothing is precomputed. Each source asks for the nodes bracketing its parameters;
a node absent from the cache is downloaded once, resampled onto a common wavelength
grid, stored, and the original payload discarded. That is about 31 KB per node
instead of 18 MB, and a catalogue only ever pays for the region it actually visits.

The spectrum is kept rather than its band fluxes for two reasons: extinction acts on
the shape of the spectrum, so it has to be applied per source and cannot be folded
into a stored flux; and a filter chosen later integrates from the cache without
fetching anything again.

What ships in the package is the node index of each family: the parameter triples
that genuinely exist. Real grids are not rectangular -- BT-Settl fills about half
of its own bounding box -- so coverage is decided by looking the nodes up, never by
a threshold in Teff.
"""

from __future__ import annotations

import csv
import os
import re
import urllib.error
import urllib.request
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from .filters import FilterCurve
from .library import user_data_root
from .phoenix import PhoenixGridCoverageError, PhoenixSpectrum, synthetic_photometry

INDEX_ROOT = Path(__file__).resolve().parent.parent / "atmospheres"

# Points the grid cache somewhere else; the test suite uses it so a developer's
# own cached nodes can never leak into a test run.
GRID_CACHE_DIR_ENV = "PHOTO_CAT_GRID_CACHE_DIR"

SVO_THEORY_BASE = "http://svo2.cab.inta-csic.es/theory/newov2/ssap.php"


class AtmosphereGridError(RuntimeError):
    """Raised when a grid node cannot be retrieved or read."""


@dataclass(frozen=True)
class AtmosphereFamily:
    """One published grid of model spectra, addressed by its own node index."""

    name: str
    svo_model: str
    index_file: str
    reference: str
    # The temperature range this code is built for. Coverage and appropriateness are
    # different things: a cool-star grid can hold a node at 40000 K and still be the
    # wrong physics there, so the regime decides which family is offered first while
    # coverage decides whether it is actually usable.
    preferred_teff: tuple[float, float] = (0.0, float("inf"))

    @property
    def index_path(self) -> Path:
        return INDEX_ROOT / self.index_file


# Ordered by preference. A point is offered to each family in turn and the first
# one whose index actually contains the bracketing nodes wins, so adding a family
# for the hot or metal-poor regime is one entry here plus its index file.
FAMILIES: tuple[AtmosphereFamily, ...] = (
    AtmosphereFamily(
        name="BT-Settl",
        svo_model="bt-settl",
        index_file="bt-settl.csv",
        reference="Allard et al. (2012), RSPTA 370, 2765; served by the SVO Theoretical Spectra Service",
        preferred_teff=(0.0, 7000.0),
    ),
    AtmosphereFamily(
        name="ATLAS9",
        svo_model="Kurucz2003",
        index_file="atlas9.csv",
        reference="Castelli & Kurucz (2003), IAU Symp. 210, A20; served by the SVO Theoretical Spectra Service",
        preferred_teff=(7000.0, 15000.0),
    ),
    AtmosphereFamily(
        name="TLUSTY",
        svo_model="tlusty_mergedbin",
        index_file="tlusty.csv",
        reference=(
            "Lanz & Hubeny (2003) OSTAR2002 and (2007) BSTAR2006, merged collection; "
            "served by the SVO Theoretical Spectra Service"
        ),
        preferred_teff=(15000.0, 55000.0),
    ),
)


@dataclass(frozen=True)
class GridNode:
    """One existing grid point and the identifier that retrieves its spectrum."""

    teff: float
    logg: float
    mh: float
    node: str
    # [alpha/Fe] of the model actually stored at this node. Gaia does not provide
    # it, so the index keeps whichever value the grid offers closest to
    # scaled-solar; recording it stops that choice from being invisible.
    alpha: float = 0.0


@dataclass(frozen=True)
class ModelSelection:
    """Which family covers a point, and why it was or was not chosen."""

    family: str | None
    reason: str
    nodes: tuple[GridNode, ...] = ()

    @property
    def covered(self) -> bool:
        return self.family is not None


class GridIndex:
    """The parameter triples one family actually provides."""

    def __init__(self, family: AtmosphereFamily) -> None:
        self.family = family
        self._nodes: dict[tuple[float, float, float], tuple[str, float]] = {}
        path = family.index_path
        if (not path.is_file()):
            raise AtmosphereGridError(
                f"Node index for family {family.name!r} is missing: {path}."
            )
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (float(row["teff"]), float(row["logg"]), float(row["mh"]))
                self._nodes[key] = (row["node"], float(row.get("alpha", 0.0)))
        self._teff = sorted({k[0] for k in self._nodes})
        self._logg = sorted({k[1] for k in self._nodes})
        self._mh = sorted({k[2] for k in self._nodes})

    def __len__(self) -> int:
        return len(self._nodes)

    @staticmethod
    def _bracket(values: list[float], point: float) -> tuple[float, float] | None:
        """Return the two axis values enclosing a point, or None when outside."""
        if (not values or point < values[0] or point > values[-1]):
            return None
        exact = bisect_left(values, point)
        if (exact < len(values) and values[exact] == point):
            return (point, point)
        upper = bisect_right(values, point)
        return (values[upper - 1], values[upper])

    def bracketing_nodes(self, teff: float, logg: float, mh: float) -> tuple[GridNode, ...] | None:
        """Return the nodes enclosing a point, or None when the family cannot cover it.

        Every corner must exist. A grid with holes would otherwise be silently
        interpolated across a gap, which is extrapolation wearing a disguise; the
        caller is expected to try the next family instead.
        """
        axes = (
            self._bracket(self._teff, teff),
            self._bracket(self._logg, logg),
            self._bracket(self._mh, mh),
        )
        if (any(axis is None for axis in axes)):
            return None
        corners: list[GridNode] = []
        resolved = [sorted(set(axis)) for axis in axes if axis is not None]
        for teff_value, logg_value, mh_value in product(*resolved):
            combination = (teff_value, logg_value, mh_value)
            entry = self._nodes.get(combination)
            if (entry is None):
                return None
            corners.append(GridNode(combination[0], combination[1], combination[2], entry[0], entry[1]))
        return tuple(corners)


@lru_cache(maxsize=8)
def load_index(family_name: str) -> GridIndex:
    """Return one family's node index, read once per process."""
    for family in FAMILIES:
        if (family.name == family_name):
            return GridIndex(family)
    raise AtmosphereGridError(f"Unknown atmosphere family {family_name!r}.")


def select_atmosphere_model(teff: float, logg: float, mh: float) -> ModelSelection:
    """Return the first family whose grid genuinely encloses the point.

    Coverage is decided by looking up the nodes, not by a threshold in Teff: real
    grids are not rectangular, so a point can sit inside a family's temperature
    range and still have no node to interpolate from.
    """
    if (not all(np.isfinite([teff, logg, mh]))):
        return ModelSelection(None, "incomplete_parameters")

    def prefers(family: AtmosphereFamily) -> bool:
        low, high = family.preferred_teff
        return low <= teff < high

    # A temperature no installed code was built for gets no model at all. Coverage is
    # a necessary condition, not a licence: a cool-star grid can hold a node at
    # 60000 K, and using it there would be the very substitution the regimes exist to
    # prevent. Such a source falls through to the caller's own fallback instead.
    preferred = [family for family in FAMILIES if prefers(family)]
    if (not preferred):
        return ModelSelection(None, "no_model_for_this_regime")

    # Within a regime the appropriate family is tried first, and the others follow
    # only as coverage fallbacks: a point can sit inside a regime and still miss a
    # node of that family, for instance at a gravity the grid does not reach.
    for family in preferred + [family for family in FAMILIES if not prefers(family)]:
        nodes = load_index(family.name).bracketing_nodes(teff, logg, mh)
        if (nodes is not None):
            reason = "covered" if prefers(family) else "covered_outside_preferred_regime"
            return ModelSelection(family.name, reason, nodes)
    return ModelSelection(None, "outside_every_grid")


def grid_cache_root() -> Path:
    """Return the directory holding cached per-node band ratios."""
    override = os.environ.get(GRID_CACHE_DIR_ENV, "").strip()
    if (override):
        return Path(override).expanduser().resolve()
    return user_data_root() / "atmosphere_grids"


# Every cached node is resampled onto this common grid before being stored. One
# nanometre is finer than any shipped passband, so integration is unaffected, and
# it turns an 18 MB download into about 31 KB on disk. Keeping the spectrum rather
# than its band fluxes is what lets extinction be applied per source, and what lets
# a filter added later be integrated without fetching anything again.
CACHE_WAVELENGTH_NM = np.arange(300.0, 8200.0 + 1.0, 1.0)


def _cache_path(family_name: str, node: str) -> Path:
    return grid_cache_root() / family_name / f"{node}.npy"


_ROW = re.compile(r"<TD>([^<]+)</TD><TD>([^<]+)</TD>")


def _download_spectrum(family: AtmosphereFamily, node: str, timeout: float) -> np.ndarray:
    """Fetch one node and return its photon density on the common wavelength grid.

    The 18 MB payload is parsed, resampled and discarded inside this call; only the
    resampled array is ever written.
    """
    url = f"{SVO_THEORY_BASE}?model={family.svo_model}&fid={node}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # noqa: S310 (fixed SVO host)
            payload = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise AtmosphereGridError(f"Could not retrieve grid node {node} from SVO: {error}") from error

    body = payload[payload.find("<TABLEDATA>"):]
    pairs = _ROW.findall(body)
    if (len(pairs) < 2):
        raise AtmosphereGridError(f"Grid node {node} returned no usable spectrum.")
    wavelength_nm = np.fromiter((float(a) for a, _ in pairs), dtype=np.float64, count=len(pairs)) / 10.0
    flux = np.fromiter((float(b) for _, b in pairs), dtype=np.float64, count=len(pairs))
    keep = np.isfinite(flux) & (wavelength_nm > 0.0)
    wavelength_nm, flux = wavelength_nm[keep], flux[keep]
    order = np.argsort(wavelength_nm)
    wavelength_nm, flux = wavelength_nm[order], flux[order]
    if (wavelength_nm[0] > CACHE_WAVELENGTH_NM[0] or wavelength_nm[-1] < CACHE_WAVELENGTH_NM[-1]):
        raise AtmosphereGridError(f"Grid node {node} does not span the cached wavelength range.")
    # F_lambda -> photon rate density: a photon at lambda carries hc/lambda, and the
    # constant drops out of every ratio taken downstream.
    return np.interp(CACHE_WAVELENGTH_NM, wavelength_nm, flux * wavelength_nm).astype(np.float32)


def node_spectrum(family_name: str, node: str, timeout: float = 300.0) -> np.ndarray:
    """Return one node's resampled photon density, downloading it only once."""
    path = _cache_path(family_name, node)
    if (path.is_file()):
        return np.load(path)
    family = next(f for f in FAMILIES if f.name == family_name)
    resampled = _download_spectrum(family, node, timeout)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, resampled)
    return resampled


class RemoteAtmosphereGrid:
    """A grid that fetches the nodes a source needs, and nothing else.

    Exposes the interface the existing PHOENIX conversion expects, so extinction,
    normalisation on Gaia G and integration through the requested filter are the
    code already written; only where the spectrum comes from is different.
    """

    def __init__(self, timeout: float = 300.0) -> None:
        self.timeout = float(timeout)
        self.index_path = INDEX_ROOT
        self.families = tuple(f.name for f in FAMILIES)
        self.last_selection: ModelSelection | None = None

    @property
    def bounds(self) -> dict[str, tuple[float, float]]:
        """Return the union of the parameter ranges the installed indexes cover."""
        spans: dict[str, tuple[float, float]] = {}
        for family in FAMILIES:
            index = load_index(family.name)
            for axis, values in (("teff", index._teff), ("logg", index._logg), ("mh", index._mh)):
                low, high = min(values), max(values)
                if (axis in spans):
                    low, high = min(low, spans[axis][0]), max(high, spans[axis][1])
                spans[axis] = (low, high)
        return spans

    def interpolate(self, teff: float, logg: float, mh: float) -> PhoenixSpectrum:
        """Return the spectrum at a point, interpolated over its bracketing nodes."""
        selection = select_atmosphere_model(teff, logg, mh)
        self.last_selection = selection
        if (not selection.covered):
            raise PhoenixGridCoverageError(
                f"(Teff={teff:g}, logg={logg:g}, [M/H]={mh:g}) is not covered by any "
                f"installed atmosphere grid: {selection.reason}."
            )

        axes = [sorted({getattr(n, a) for n in selection.nodes}) for a in ("teff", "logg", "mh")]
        fractions = []
        for axis, value in zip(axes, (teff, logg, mh)):
            if (len(axis) == 1 or axis[-1] == axis[0]):
                fractions.append(0.0)
            else:
                fractions.append((value - axis[0]) / (axis[-1] - axis[0]))

        total = np.zeros(CACHE_WAVELENGTH_NM.shape, dtype=np.float64)
        for node in selection.nodes:
            share = 1.0
            for axis, fraction, value in zip(axes, fractions, (node.teff, node.logg, node.mh)):
                share *= (1.0 - fraction) if (value == axis[0]) else fraction
            if (share <= 0.0):
                continue
            total += share * node_spectrum(str(selection.family), node.node, self.timeout)
        if (not np.any(total > 0.0)):
            raise PhoenixGridCoverageError("Interpolated atmosphere spectrum is empty.")
        return PhoenixSpectrum(
            wavelength_nm=CACHE_WAVELENGTH_NM,
            photon_flux_density=total,
            band_weight=CACHE_WAVELENGTH_NM,
        )


def cached_node_count(family_name: str | None = None) -> int:
    """Return how many nodes the local cache already holds."""
    root = grid_cache_root()
    families: Iterable[Path] = [root / family_name] if family_name else (
        [p for p in root.iterdir() if p.is_dir()] if root.is_dir() else []
    )
    return sum(len(list(path.glob("*.npy"))) for path in families if path.is_dir())

def node_band_fluxes(
    family_name: str,
    node: str,
    curves: dict[str, FilterCurve],
    timeout: float = 300.0,
) -> dict[str, float]:
    """Return one node's flux in each filter, integrating its spectrum once."""
    # Built as the spectrum the slow path would have used and pushed through the
    # same integrator, so the two routes cannot drift apart on a convention.
    spectrum = PhoenixSpectrum(
        wavelength_nm=CACHE_WAVELENGTH_NM,
        photon_flux_density=node_spectrum(family_name, node, timeout).astype(np.float64),
        band_weight=CACHE_WAVELENGTH_NM,
    )
    return {band: synthetic_photometry(spectrum, curve) for band, curve in curves.items()}


def blend_weights(selection: ModelSelection, teff: float, logg: float, mh: float) -> list[float]:
    """Return each corner's share of a trilinear blend, in ``selection.nodes`` order."""
    axes = [sorted({getattr(n, a) for n in selection.nodes}) for a in ("teff", "logg", "mh")]
    fractions = [
        0.0 if (len(axis) == 1 or axis[-1] == axis[0]) else (value - axis[0]) / (axis[-1] - axis[0])
        for axis, value in zip(axes, (teff, logg, mh))
    ]
    weights = []
    for node in selection.nodes:
        share = 1.0
        for axis, fraction, value in zip(axes, fractions, (node.teff, node.logg, node.mh)):
            share *= (1.0 - fraction) if (value == axis[0]) else fraction
        weights.append(share)
    return weights


def batch_band_fluxes(
    selections: Iterable[ModelSelection],
    curves: dict[str, FilterCurve],
    timeout: float = 300.0,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, dict[str, float]]:
    """Integrate every distinct node one catalogue needs, once each.

    Integration is linear in the spectrum, so blending the corner spectra and then
    integrating gives exactly the same number as integrating the corners and then
    blending. Doing it in this order turns a per-source integral -- and a possible
    download inside a per-source loop -- into one pass over the distinct nodes,
    which for any catalogue is bounded by the grid rather than by its own size.
    """
    wanted: dict[str, str] = {}
    for selection in selections:
        if (selection.covered):
            for node in selection.nodes:
                wanted.setdefault(node.node, str(selection.family))

    fluxes: dict[str, dict[str, float]] = {}
    total = len(wanted)
    for position, (node_id, family_name) in enumerate(sorted(wanted.items()), start=1):
        if (progress is not None):
            progress(position, total)
        fluxes[node_id] = node_band_fluxes(family_name, node_id, curves, timeout)
    return fluxes
