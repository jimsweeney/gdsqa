"""LayerStack / PDK technology checks.

Validates a process stack (the technology definition, not a layout): per-level metadata (material, thickness,
tolerances, layer), vertical geometry (z-overlap between distinct grown layers, optional gaps), and the
(layer, datatype) map (duplicate grown layers, derived-layer collisions and duplicates).
"""
from __future__ import annotations
from dataclasses import dataclass

_FIELDS = ("layer", "zmin", "thickness", "material", "derived_layer",
           "thickness_tolerance", "zmin_tolerance", "sidewall_angle")
_EPS = 1e-9


@dataclass
class Level:
    name: str
    layer: tuple = None
    zmin: float = None
    thickness: float = None
    material: str = None
    derived_layer: tuple = None
    thickness_tolerance: float = None
    zmin_tolerance: float = None
    sidewall_angle: float = None

    @property
    def zmax(self):
        if self.zmin is None or self.thickness is None:
            return None
        return self.zmin + self.thickness


@dataclass
class Stack:
    levels: list


def _as_layer(layer):
    if layer is None:
        return None
    if isinstance(layer, int):
        return (layer, 0)
    t = tuple(int(v) for v in layer)
    return (t[0], 0) if len(t) == 1 else (t[0], t[1])


def from_levels(levels):
    out = []
    for name, spec in levels.items():
        spec = dict(spec)
        kw = {k: spec.get(k) for k in _FIELDS}
        kw["layer"] = _as_layer(kw["layer"])
        kw["derived_layer"] = _as_layer(kw["derived_layer"])
        out.append(Level(name=name, **kw))
    return Stack(out)


def from_layerstack(layerstack):
    layers = layerstack.layers if hasattr(layerstack, "layers") else layerstack
    return from_levels({name: {k: getattr(level, k, None) for k in _FIELDS}
                        for name, level in layers.items()})


def check_levels(stack):
    issues = []
    seen = set()
    for lv in stack.levels:
        if lv.name in seen:
            issues.append({"rule": "duplicate_name", "severity": "error",
                           "message": f"level name '{lv.name}' is used more than once"})
        seen.add(lv.name)
        if not lv.material:
            issues.append({"rule": "missing_material", "severity": "warning",
                           "message": f"level '{lv.name}' has no material"})
        if lv.thickness is None:
            issues.append({"rule": "missing_thickness", "severity": "warning",
                           "message": f"level '{lv.name}' has no thickness"})
        elif lv.thickness <= 0:
            issues.append({"rule": "nonpositive_thickness", "severity": "error",
                           "message": f"level '{lv.name}' has thickness {lv.thickness}"})
        if lv.zmin is None:
            issues.append({"rule": "missing_zmin", "severity": "warning",
                           "message": f"level '{lv.name}' has no zmin"})
        if lv.layer is None:
            issues.append({"rule": "missing_layer", "severity": "warning",
                           "message": f"level '{lv.name}' has no GDS layer"})
        for field in ("thickness_tolerance", "zmin_tolerance"):
            tol = getattr(lv, field)
            if tol is not None and tol < 0:
                issues.append({"rule": "negative_tolerance", "severity": "error",
                               "message": f"level '{lv.name}' has {field} {tol} < 0"})
        if (lv.thickness_tolerance is not None and lv.thickness is not None
                and lv.thickness > 0 and lv.thickness_tolerance >= lv.thickness):
            issues.append({"rule": "tolerance_exceeds_value", "severity": "warning",
                           "message": f"level '{lv.name}' thickness_tolerance {lv.thickness_tolerance} "
                                      f">= thickness {lv.thickness}"})
    return issues


def check_zstack(stack, allow_overlap=None, report_gaps=False):
    allow = {frozenset(p) for p in allow_overlap} if allow_overlap else set()
    levels = [lv for lv in stack.levels
              if lv.zmin is not None and lv.thickness is not None and lv.thickness > 0]
    issues = []
    for i in range(len(levels)):
        for j in range(i + 1, len(levels)):
            a, b = levels[i], levels[j]
            overlap = min(a.zmax, b.zmax) - max(a.zmin, b.zmin)
            if overlap > _EPS and frozenset((a.name, b.name)) not in allow:
                issues.append({"rule": "z_overlap", "severity": "warning",
                               "message": f"levels '{a.name}' [{a.zmin}, {a.zmax}] and '{b.name}' "
                                          f"[{b.zmin}, {b.zmax}] overlap by {overlap:.4g} in z"})
    if report_gaps:
        ordered = sorted(levels, key=lambda lv: lv.zmin)
        for a, b in zip(ordered, ordered[1:]):
            gap = b.zmin - a.zmax
            if gap > _EPS:
                issues.append({"rule": "z_gap", "severity": "warning",
                               "message": f"vertical gap of {gap:.4g} between '{a.name}' and '{b.name}'"})
    return issues


def check_derived(stack):
    issues = []
    grown = {}
    for lv in stack.levels:
        if lv.layer is not None:
            grown.setdefault(lv.layer, []).append(lv.name)
    for layer, names in grown.items():
        if len(names) > 1:
            issues.append({"rule": "duplicate_layer", "severity": "warning",
                           "message": f"layer {layer} is the grown layer of levels {tuple(names)}"})
    derived = {}
    for lv in stack.levels:
        if lv.derived_layer is None:
            continue
        derived.setdefault(lv.derived_layer, []).append(lv.name)
        if lv.derived_layer in grown and lv.name not in grown[lv.derived_layer]:
            issues.append({"rule": "derived_collision", "severity": "warning",
                           "message": f"level '{lv.name}' derives onto layer {lv.derived_layer}, "
                                      f"the grown layer of {tuple(grown[lv.derived_layer])}"})
    for layer, names in derived.items():
        if len(names) > 1:
            issues.append({"rule": "derived_duplicate", "severity": "warning",
                           "message": f"levels {tuple(names)} all derive onto layer {layer}"})
    return issues


def check(stack, allow_overlap=None, report_gaps=False):
    """Run every stack check."""
    return (check_levels(stack)
            + check_zstack(stack, allow_overlap=allow_overlap, report_gaps=report_gaps)
            + check_derived(stack))
