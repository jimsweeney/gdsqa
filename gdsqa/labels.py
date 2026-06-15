"""Text/label checks.

On the flattened geometry of a layout, flags labels that sit on no geometry (orphans), duplicate and empty
labels, and labels on a layer that holds no geometry (unless that layer is a declared text layer).
"""
from __future__ import annotations


def _check_placement(layout):
    polys = [p for group in layout.polys.values() for p in group]
    if not polys or not layout.labels:
        return []
    import gdstk
    import numpy as np

    gpolys = [gdstk.Polygon(np.asarray(p, float)) for p in polys]
    points = [pos for _layer, _text, pos in layout.labels]
    inside = gdstk.inside(points, gpolys)
    issues = []
    for (_layer, text, pos), on_geom in zip(layout.labels, inside):
        if not on_geom:
            issues.append({"rule": "orphan_label", "severity": "warning",
                           "message": f"label '{text}' at {pos} is not on any geometry"})
    return issues


def _check_text(layout, grid=1e-3):
    issues = []
    seen = {}
    for _layer, text, pos in layout.labels:
        if not text.strip():
            issues.append({"rule": "empty_label", "severity": "warning",
                           "message": f"label at {pos} has empty text"})
            continue
        key = (text, int(round(pos[0] / grid)), int(round(pos[1] / grid)))
        seen[key] = seen.get(key, 0) + 1
    for (text, _sx, _sy), count in sorted(seen.items()):
        if count > 1:
            issues.append({"rule": "duplicate_label", "severity": "warning",
                           "message": f"label '{text}' appears {count} times at the same position"})
    return issues


def _check_layers(layout, text_layers=()):
    allowed = set(text_layers)
    geom = layout.geometry_layers
    issues = []
    for (layer, _texttype), text, _pos in layout.labels:
        if layer not in geom and layer not in allowed:
            issues.append({"rule": "label_on_empty_layer", "severity": "warning",
                           "message": f"label '{text}' is on layer {layer}, which has no geometry "
                                      f"(declare it as a text layer if that is intended)"})
    return issues


def check(layout, text_layers=(), grid=1e-3):
    """Run every label check."""
    return _check_placement(layout) + _check_text(layout, grid) + _check_layers(layout, text_layers)
