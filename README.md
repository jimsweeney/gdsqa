# gdsqa - quality-assurance checks for gdsfactory

![tests](https://github.com/jimsweeney/gdsqa/actions/workflows/ci.yml/badge.svg) ![license](https://img.shields.io/badge/license-MIT-blue.svg)

`gdsqa` is a small QA suite for gdsfactory designs. It runs four families of checks behind one issue format
and one CLI, catching the authoring mistakes that geometry DRC and netlist extraction miss:

- **ports** - port-metadata and connection-compatibility checks (including the connection width mismatch that
  `get_netlist` does not flag),
- **stack** - LayerStack / PDK technology consistency checks,
- **hierarchy** - dead cells, duplicate-geometry cells, empty cells, wrapper chains, reference cycles,
- **labels** - orphan, duplicate, empty, and wrong-layer text labels.

Every check returns the same `{rule, severity, message}` issue shape, so the report looks the same no matter
which checks ran.

## Install

```
pip install .
```

That installs `numpy` and `gdstk` and adds a `gdsqa` command. To run from a clone without installing, use
`pip install -r requirements.txt` and call `python -m gdsqa.cli` instead. `gdsfactory` is optional and only
needed to read a `Component` directly; GDS files and JSON specs work without it.

## Use

The CLI has three subcommands, by input type (after `pip install .`; without installing, use
`python -m gdsqa.cli` in place of `gdsqa`):

```
gdsqa layout chip.gds --text-layers 10 11 -o out/   # hierarchy + label checks on a GDS
gdsqa ports  model.json -o out/                     # port + connection checks
gdsqa stack  stack.json -o out/                     # LayerStack checks
```

Each writes `report.json` and `report.md`, and exits non-zero if any error-severity issue is found, so it
drops straight into a CI job.

The `ports` model and `stack` spec are small JSON files:

```json
// ports
{"ports": [{"name": "o1", "center": [0, 0], "width": 0.5, "orientation": 180, "layer": [1, 0]}],
 "bbox": [-1, -1, 11, 1], "grid": 0.001, "allowed_layers": [[1, 0]], "connections": [["o1", "o2"]]}
```
```json
// stack
{"levels": {"core": {"layer": [1, 0], "zmin": 0.0, "thickness": 0.22, "material": "si"}},
 "allow_overlap": [["core", "clad"]]}
```

From Python:

```python
from gdsqa import layout, ports, stack, hierarchy, labels, issues, lint_layout

model = layout.from_gds("chip.gds")             # or layout.from_component(component)
print(issues.to_markdown(lint_layout(model, text_layers={10})))

print(ports.check(ports.from_component(component)))
print(stack.check(stack.from_layerstack(layer_stack)))
```

A runnable example is in `examples/quickstart.py`.

## Checks

| Family | Rules |
|---|---|
| ports | `duplicate_name`, `off_grid`, `outside_bbox`, `nonpositive_width`, `bad_layer`, `width_mismatch`, `layer_mismatch`, `orientation_mismatch`, `missing_port` |
| stack | `duplicate_name`, `missing_material`, `missing_thickness`, `nonpositive_thickness`, `missing_zmin`, `missing_layer`, `negative_tolerance`, `tolerance_exceeds_value`, `z_overlap`, `z_gap`, `duplicate_layer`, `derived_collision`, `derived_duplicate` |
| hierarchy | `reference_cycle`, `orphan_root`, `dead_cell`, `duplicate_geometry`, `empty_cell`, `wrapper_chain` |
| labels | `orphan_label`, `duplicate_label`, `empty_label`, `label_on_empty_layer` |

## Sample report

```
# gdsqa layout

0 error(s), 5 warning(s)

## Warnings
- [orphan_root] cell 'scratch' is a top-level cell but not the main top 'top'
- [duplicate_geometry] cells ('leaf', 'leaf_copy') have identical content (dedup opportunity)
- [empty_cell] cell 'scratch' is empty (no geometry, labels, or references)
- [wrapper_chain] wrapper chain 3 deep: w1 -> w2 -> w3
- [orphan_label] label 'stray' at (50.0, 50.0) is not on any geometry
```

## Package layout

| Module | What it does |
|---|---|
| `gdsqa/issues.py` | the shared issue format: JSON and Markdown by severity |
| `gdsqa/ports.py` | port and connection checks |
| `gdsqa/stack.py` | LayerStack / PDK technology checks |
| `gdsqa/layout.py` | read a GDS / Component into the cell graph plus flattened geometry |
| `gdsqa/hierarchy.py` | hierarchy and cell-hygiene checks |
| `gdsqa/labels.py` | text/label checks |
| `gdsqa/cli.py` | the `layout` / `ports` / `stack` command line |

## Test

```
python run_checks.py suite     # pytest tests/
```

Each check is validated against a constructed input with a known issue: a connection of mismatched widths is
flagged, a level whose tolerance exceeds its thickness is flagged, a cell reachable only from a floating root
is dead, and a label in empty space is an orphan.

## Scope

gdsqa validates metadata, hierarchy, and labels. It does not run geometry DRC and does not extract a netlist
from polygons; it complements gdsfactory's own checks rather than replacing them. The hierarchy and label
checks run on a flattened view of the layout.
