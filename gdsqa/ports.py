"""Port and connection checks.

Catches the port-metadata and connection-compatibility mistakes that geometry DRC and netlist extraction miss:
off-grid or out-of-bounds ports, duplicate names, ports on an undeclared layer, zero-width ports, and
connections that join ports of different width, layer, or orientation (the width mismatch that gdsfactory's
get_netlist does not flag).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Port:
    name: str
    center: tuple
    width: float
    orientation: float
    layer: tuple


@dataclass
class Model:
    ports: list
    bbox: tuple = (0.0, 0.0, 0.0, 0.0)
    grid: float = 0.001
    allowed_layers: tuple = None


def from_ports(ports, bbox, grid=0.001, allowed_layers=None):
    out = []
    for p in ports:
        if isinstance(p, dict):
            p = dict(p)
            p["center"] = tuple(p["center"])
            if p.get("layer") is not None:
                p["layer"] = tuple(p["layer"])
            out.append(Port(**p))
        else:
            out.append(p)
    al = tuple(tuple(layer) for layer in allowed_layers) if allowed_layers is not None else None
    return Model(out, tuple(float(v) for v in bbox), float(grid), al)


def from_component(component, grid=0.001, allowed_layers=None):
    """Best-effort extraction of ports and bbox from a gdsfactory Component."""
    import numpy as np

    items = component.ports.values() if hasattr(component.ports, "values") else component.ports
    ports = []
    for p in items:
        layer = tuple(p.layer) if getattr(p, "layer", None) is not None else None
        ports.append(Port(p.name, tuple(float(c) for c in p.center), float(p.width),
                          float(p.orientation), layer))
    arr = np.asarray(component.bbox, float).ravel()
    bbox = (float(arr[0]), float(arr[1]), float(arr[2]), float(arr[3]))
    return from_ports(ports, bbox, grid, allowed_layers)


def _on_grid(value, grid, eps=1e-9):
    r = value / grid
    return abs(r - round(r)) < eps


def check_ports(model):
    """Port-metadata issues for a model."""
    issues = []
    xmin, ymin, xmax, ymax = model.bbox
    tol = model.grid
    seen = set()
    for p in model.ports:
        if p.name in seen:
            issues.append({"rule": "duplicate_name", "severity": "error",
                           "message": f"port name '{p.name}' is used more than once"})
        seen.add(p.name)
        x, y = p.center
        if not (_on_grid(x, model.grid) and _on_grid(y, model.grid)):
            issues.append({"rule": "off_grid", "severity": "warning",
                           "message": f"port '{p.name}' centre {p.center} is not on the {model.grid} um grid"})
        if not (xmin - tol <= x <= xmax + tol and ymin - tol <= y <= ymax + tol):
            issues.append({"rule": "outside_bbox", "severity": "warning",
                           "message": f"port '{p.name}' centre {p.center} is outside the cell bbox"})
        if p.width <= 0:
            issues.append({"rule": "nonpositive_width", "severity": "error",
                           "message": f"port '{p.name}' has width {p.width}"})
        if model.allowed_layers is not None and p.layer not in model.allowed_layers:
            issues.append({"rule": "bad_layer", "severity": "error",
                           "message": f"port '{p.name}' is on layer {p.layer}, not in the allowed set"})
    return issues


def check_connections(model, connections, width_tol=1e-3, angle_tol=1.0):
    """Connection-compatibility issues. `connections` is a list of (port_name_a, port_name_b)."""
    by_name = {p.name: p for p in model.ports}
    issues = []
    for a, b in connections:
        pa, pb = by_name.get(a), by_name.get(b)
        if pa is None or pb is None:
            issues.append({"rule": "missing_port", "severity": "error",
                           "message": f"connection ({a}, {b}) references a port that does not exist"})
            continue
        if abs(pa.width - pb.width) > width_tol:
            issues.append({"rule": "width_mismatch", "severity": "error",
                           "message": f"{a} width {pa.width} != {b} width {pb.width}"})
        if pa.layer != pb.layer:
            issues.append({"rule": "layer_mismatch", "severity": "error",
                           "message": f"{a} layer {pa.layer} != {b} layer {pb.layer}"})
        if abs((pa.orientation - pb.orientation) % 360 - 180) > angle_tol:
            issues.append({"rule": "orientation_mismatch", "severity": "warning",
                           "message": f"{a} ({pa.orientation} deg) and {b} ({pb.orientation} deg) "
                                      f"do not face each other"})
    return issues


def check(model, connections=None):
    """Run the port checks (and connection checks if connections are given)."""
    issues = check_ports(model)
    if connections:
        issues += check_connections(model, connections)
    return issues
