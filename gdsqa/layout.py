"""Shared layout model for the GDS-based checks.

Reads a GDS file or a gdsfactory Component once and provides two views: the cell reference graph (used by the
hierarchy checks) and the flattened geometry, with labels and polygons by layer (used by the label checks). The
cell graph is captured before the top cell is flattened, so both views are consistent.
"""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field

import numpy as np


@dataclass
class CellInfo:
    name: str
    refs: list = field(default_factory=list)     # child cell names
    n_polygons: int = 0
    n_labels: int = 0
    geo_sig: str = ""


@dataclass
class Layout:
    cells: dict = field(default_factory=dict)            # {name: CellInfo} (reference graph)
    top: list = field(default_factory=list)              # top-level cell names
    labels: list = field(default_factory=list)           # flattened [((layer, texttype), text, (x, y))]
    polys: dict = field(default_factory=dict)            # flattened {(layer, datatype): [point arrays]}

    @property
    def geometry_layers(self):
        return {layer for (layer, _dt) in self.polys}


def _geo_sig(cell, grid):
    items = []
    for poly in cell.polygons:
        pts = tuple((int(round(x / grid)), int(round(y / grid))) for x, y in poly.points)
        items.append(((int(poly.layer), int(poly.datatype)), pts))
    items.sort()
    return hashlib.md5(repr(items).encode("utf-8")).hexdigest()


def _descendants(cells, name):
    seen, stack = set(), [c for c in cells.get(name, CellInfo(name)).refs if c in cells]
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(c for c in cells[n].refs if c in cells)
    return seen


def from_gdstk_library(lib, grid=1e-3):
    cells = {}
    for c in lib.cells:
        refs = [r.cell.name if hasattr(r.cell, "name") else str(r.cell) for r in c.references]
        cells[c.name] = CellInfo(c.name, refs, len(c.polygons), len(c.labels), _geo_sig(c, grid))
    tops = lib.top_level() if hasattr(lib, "top_level") else []
    top = [t.name for t in tops]

    primary = None
    if len(top) == 1:
        primary = tops[0]
    elif top:
        best = max(top, key=lambda t: len(_descendants(cells, t)))
        primary = next(t for t in tops if t.name == best)
    elif lib.cells:
        primary = lib.cells[0]

    labels, polys = [], {}
    if primary is not None:
        primary.flatten()
        for p in primary.polygons:
            polys.setdefault((int(p.layer), int(p.datatype)), []).append(np.asarray(p.points, float))
        labels = [((int(la.layer), int(getattr(la, "texttype", 0))), str(la.text),
                   (float(la.origin[0]), float(la.origin[1]))) for la in primary.labels]
    return Layout(cells, top, labels, polys)


def from_gds(path, grid=1e-3):
    import gdstk
    return from_gdstk_library(gdstk.read_gds(path), grid)


def from_component(component, grid=1e-3):
    cell = getattr(component, "_cell", None)
    if cell is not None and getattr(cell, "library", None) is not None:
        return from_gdstk_library(cell.library, grid)
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "c.gds")
        component.write_gds(path)
        return from_gds(path, grid)
