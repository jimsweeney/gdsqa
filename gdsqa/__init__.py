"""gdsqa - quality-assurance checks for gdsfactory layouts and technology.

Four families of checks behind one issue format:
  - ports:     port-metadata and connection-compatibility checks (a Component or a port/connection model)
  - stack:     LayerStack / PDK technology consistency checks (a LayerStack or a level dict)
  - hierarchy: dead cells, duplicate geometry, empty cells, wrapper chains, reference cycles (a GDS layout)
  - labels:    orphan, duplicate, empty, and wrong-layer text labels (a GDS layout)

Each check returns a list of issue dicts; issues.to_json / issues.to_markdown render any of them.
"""
from . import issues, ports, stack, layout, hierarchy, labels

__all__ = ["issues", "ports", "stack", "layout", "hierarchy", "labels", "lint_layout"]


def lint_layout(layout_model, text_layers=(), min_chain_depth=3):
    """Run the GDS-based checks (hierarchy + labels) on a loaded layout and return the combined issues."""
    return hierarchy.check(layout_model, min_chain_depth=min_chain_depth) \
        + labels.check(layout_model, text_layers=text_layers)
