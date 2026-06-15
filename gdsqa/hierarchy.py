"""Hierarchy and cell-hygiene checks.

On the cell reference graph of a layout, flags dead cells (unreachable from the main top), orphan root cells,
reference cycles, cells that draw identical geometry under different names, empty cells, and deep single-child
wrapper chains.
"""
from __future__ import annotations


def _refs(cells, name):
    info = cells.get(name)
    return [c for c in (info.refs if info else []) if c in cells]


def _descendants(cells, name):
    seen, stack = set(), list(_refs(cells, name))
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(_refs(cells, n))
    return seen


def _reachable(cells, roots):
    seen, stack = set(), list(roots)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(_refs(cells, n))
    return seen


def primary_top(layout):
    tops = layout.top or list(layout.cells)
    return max(tops, key=lambda t: len(_descendants(layout.cells, t))) if tops else None


def _check_graph(layout):
    cells = layout.cells
    issues = []
    color, in_cycle = {}, set()

    def dfs(n, path):
        color[n] = 0
        path.append(n)
        for c in _refs(cells, n):
            if color.get(c) == 0:
                in_cycle.update(path[path.index(c):])
            elif c not in color:
                dfs(c, path)
        color[n] = 1
        path.pop()

    for n in list(cells):
        if n not in color:
            dfs(n, [])
    if in_cycle:
        issues.append({"rule": "reference_cycle", "severity": "error",
                       "message": f"reference cycle through cells {tuple(sorted(in_cycle))}"})

    top = primary_top(layout)
    reach = _reachable(cells, [top]) if top else set()
    orphan_roots = set(layout.top) - {top}
    for t in sorted(orphan_roots):
        issues.append({"rule": "orphan_root", "severity": "warning",
                       "message": f"cell '{t}' is a top-level cell but not the main top '{top}'"})
    for name in sorted(cells):
        if name not in reach and name not in orphan_roots:
            issues.append({"rule": "dead_cell", "severity": "warning",
                           "message": f"cell '{name}' is not reachable from the top '{top}'"})
    return issues


def _check_dupcells(layout):
    groups = {}
    for name, info in layout.cells.items():
        if info.n_polygons == 0 and not info.refs:
            continue
        key = (info.geo_sig, tuple(sorted(info.refs)))
        groups.setdefault(key, []).append(name)
    issues = []
    for names in sorted(sorted(g) for g in groups.values() if len(g) > 1):
        issues.append({"rule": "duplicate_geometry", "severity": "warning",
                       "message": f"cells {tuple(names)} have identical content (dedup opportunity)"})
    return issues


def _check_chains(layout, min_chain_depth=3):
    cells = layout.cells
    issues = []
    for name in sorted(cells):
        info = cells[name]
        if info.n_polygons == 0 and info.n_labels == 0 and not info.refs:
            issues.append({"rule": "empty_cell", "severity": "warning",
                           "message": f"cell '{name}' is empty (no geometry, labels, or references)"})
    wrappers = {n: i.refs[0] for n, i in cells.items()
                if i.n_polygons == 0 and i.n_labels == 0 and len(i.refs) == 1}
    children = set(wrappers.values())
    for head in wrappers:
        if head in children:
            continue
        chain, n = [], head
        while n in wrappers:
            chain.append(n)
            n = wrappers[n]
        if len(chain) >= min_chain_depth:
            issues.append({"rule": "wrapper_chain", "severity": "warning",
                           "message": f"wrapper chain {len(chain)} deep: {' -> '.join(chain)}"})
    return issues


def check(layout, min_chain_depth=3):
    """Run every hierarchy check."""
    return _check_graph(layout) + _check_dupcells(layout) + _check_chains(layout, min_chain_depth)
