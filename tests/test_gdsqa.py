"""Test suite for gdsqa."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gdstk

from gdsqa import issues, ports, stack, layout, hierarchy, labels, lint_layout
from gdsqa import cli


# ---- ports ---------------------------------------------------------------

def test_ports_clean_and_faulty():
    clean = ports.from_ports(
        [dict(name="o1", center=(0.0, 0.0), width=0.5, orientation=180.0, layer=(1, 0)),
         dict(name="o2", center=(10.0, 0.0), width=0.5, orientation=0.0, layer=(1, 0))],
        bbox=(-1, -1, 11, 1), grid=0.001, allowed_layers=[(1, 0)])
    assert ports.check_ports(clean) == []
    faulty = ports.from_ports(
        [dict(name="a", center=(0.0, 0.0), width=0.5, orientation=0.0, layer=(1, 0)),
         dict(name="a", center=(0.0005, 0.0), width=0.0, orientation=0.0, layer=(9, 0))],
        bbox=(-1, -1, 11, 1), grid=0.001, allowed_layers=[(1, 0)])
    rules = {i["rule"] for i in ports.check_ports(faulty)}
    assert {"duplicate_name", "off_grid", "nonpositive_width", "bad_layer"} <= rules


def test_ports_connections():
    m = ports.from_ports([
        dict(name="o1", center=(0.0, 0.0), width=0.5, orientation=0.0, layer=(1, 0)),
        dict(name="o2", center=(10.0, 0.0), width=0.5, orientation=180.0, layer=(1, 0)),
        dict(name="o3", center=(0.0, 5.0), width=0.8, orientation=180.0, layer=(1, 0)),
    ], bbox=(-1, -1, 11, 8))
    assert ports.check_connections(m, [("o1", "o2")]) == []
    rules = {i["rule"] for i in ports.check_connections(m, [("o1", "o3"), ("o1", "x")])}
    assert {"width_mismatch", "missing_port"} <= rules


# ---- stack ---------------------------------------------------------------

def test_stack_clean_and_faulty():
    clean = stack.from_levels({
        "m1": dict(layer=(1, 0), zmin=0.0, thickness=0.5, material="al"),
        "m2": dict(layer=(2, 0), zmin=1.0, thickness=0.5, material="al"),
    })
    assert stack.check(clean) == []
    faulty = stack.from_levels({
        "nomat": dict(layer=(1, 0), zmin=0.0, thickness=0.5),                 # no material; overlaps 'dup'
        "dup": dict(layer=(1, 0), zmin=0.3, thickness=0.5, material="al"),    # same layer as nomat -> dup + overlap
        "thin": dict(layer=(3, 0), zmin=5.0, thickness=0.0, material="x"),    # nonpositive thickness
    })
    rules = {i["rule"] for i in stack.check(faulty)}
    assert {"missing_material", "nonpositive_thickness", "duplicate_layer", "z_overlap"} <= rules


# ---- layout fixtures -----------------------------------------------------

def _hier_lib():
    lib = gdstk.Library("h")
    leaf = lib.new_cell("leaf"); leaf.add(gdstk.rectangle((0, 0), (1, 1), layer=1))
    leaf2 = lib.new_cell("leaf2"); leaf2.add(gdstk.rectangle((0, 0), (1, 1), layer=1))   # dup geometry
    w3 = lib.new_cell("w3"); w3.add(gdstk.Reference(leaf, (0, 0)))
    w2 = lib.new_cell("w2"); w2.add(gdstk.Reference(w3, (0, 0)))
    w1 = lib.new_cell("w1"); w1.add(gdstk.Reference(w2, (0, 0)))                          # 3-deep chain
    top = lib.new_cell("top")
    top.add(gdstk.Reference(w1, (0, 0))); top.add(gdstk.Reference(leaf2, (5, 0)))
    top.add(gdstk.rectangle((0, 0), (9, 9), layer=2))
    floating = lib.new_cell("floating"); buried = lib.new_cell("buried")
    floating.add(gdstk.Reference(buried, (0, 0))); buried.add(gdstk.rectangle((0, 0), (1, 1), layer=3))
    lib.new_cell("blank")                                                                  # empty cell
    return lib


def _label_lib():
    lib = gdstk.Library("l")
    c = lib.new_cell("c")
    c.add(gdstk.rectangle((0, 0), (4, 4), layer=1))
    c.add(gdstk.Label("pin", (2, 2), layer=10))      # on the rect, pin layer
    c.add(gdstk.Label("stray", (20, 20), layer=10))  # in empty space
    c.add(gdstk.Label("", (2, 2), layer=10))         # empty
    c.add(gdstk.Label("typo", (2, 2), layer=99))     # geometry-free layer
    return lib


# ---- hierarchy -----------------------------------------------------------

def test_hierarchy():
    lo = layout.from_gdstk_library(_hier_lib())
    rules = {i["rule"] for i in hierarchy.check(lo)}
    assert {"orphan_root", "dead_cell", "duplicate_geometry", "empty_cell", "wrapper_chain"} <= rules


def test_hierarchy_cycle():
    lib = gdstk.Library("c")
    a = lib.new_cell("A"); b = lib.new_cell("B")
    a.add(gdstk.Reference(b, (0, 0))); b.add(gdstk.Reference(a, (0, 0)))
    lo = layout.from_gdstk_library(lib)
    assert "reference_cycle" in {i["rule"] for i in hierarchy.check(lo)}


# ---- labels --------------------------------------------------------------

def test_labels():
    lo = layout.from_gdstk_library(_label_lib())
    rules = {i["rule"] for i in labels.check(lo, text_layers={10})}
    assert {"orphan_label", "empty_label", "label_on_empty_layer"} <= rules
    # the pin label on layer 10 (a declared text layer) must not be flagged for its layer
    assert not any("pin" in i["message"] and i["rule"] == "label_on_empty_layer"
                   for i in labels.check(lo, text_layers={10}))


def test_lint_layout_and_clean_markdown():
    lo = layout.from_gdstk_library(_label_lib())
    assert len(lint_layout(lo, text_layers={10})) > 0
    assert issues.to_markdown([]) == "# gdsqa\n\nNo issues found."


# ---- cli -----------------------------------------------------------------

def test_cli_layout(tmp_path):
    gds = str(tmp_path / "h.gds")
    _hier_lib().write_gds(gds)
    out = cli.run_layout(gds, str(tmp_path / "out"))
    assert os.path.exists(out["markdown"]) and out["n_issues"] > 0
    assert "# gdsqa layout" in open(out["markdown"], encoding="utf-8").read()


def test_cli_ports(tmp_path):
    spec = {"ports": [{"name": "o1", "center": [0, 0], "width": 0.0, "orientation": 0, "layer": [2, 0]},
                      {"name": "o2", "center": [10, 0], "width": 0.5, "orientation": 180, "layer": [1, 0]}],
            "bbox": [-1, -1, 11, 1], "grid": 0.001, "allowed_layers": [[1, 0]],
            "connections": [["o1", "o2"]]}
    src = str(tmp_path / "m.json")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    out = cli.run_ports(src, str(tmp_path / "out"))
    md = open(out["markdown"], encoding="utf-8").read()
    assert "width_mismatch" in md and "bad_layer" in md and out["n_errors"] > 0


def test_cli_stack(tmp_path):
    spec = {"levels": {"nomat": {"layer": [1, 0], "zmin": 0.0, "thickness": 0.0},
                       "dup": {"layer": [1, 0], "zmin": 0.3, "thickness": 0.5, "material": "al"}}}
    src = str(tmp_path / "s.json")
    with open(src, "w", encoding="utf-8") as f:
        json.dump(spec, f)
    out = cli.run_stack(src, str(tmp_path / "out"))
    assert "nonpositive_thickness" in open(out["markdown"], encoding="utf-8").read()


def test_cli_missing_file(tmp_path):
    import pytest
    with pytest.raises(SystemExit):
        cli.run_layout(str(tmp_path / "nope.gds"), str(tmp_path / "out"))
