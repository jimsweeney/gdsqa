"""Run the gdsqa layout checks on a small, deliberately messy GDS and print the report.

Run from the repo root:  python examples/quickstart.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gdstk

from gdsqa import issues, layout, lint_layout


def _messy():
    lib = gdstk.Library("messy")
    leaf = lib.new_cell("leaf"); leaf.add(gdstk.rectangle((0, 0), (1, 1), layer=1))
    twin = lib.new_cell("leaf_copy"); twin.add(gdstk.rectangle((0, 0), (1, 1), layer=1))   # dup geometry
    w3 = lib.new_cell("w3"); w3.add(gdstk.Reference(leaf, (0, 0)))
    w2 = lib.new_cell("w2"); w2.add(gdstk.Reference(w3, (0, 0)))
    w1 = lib.new_cell("w1"); w1.add(gdstk.Reference(w2, (0, 0)))                            # 3-deep chain
    top = lib.new_cell("top")
    top.add(gdstk.Reference(w1, (0, 0))); top.add(gdstk.Reference(twin, (5, 0)))
    top.add(gdstk.rectangle((0, 0), (10, 10), layer=1))
    top.add(gdstk.Label("good", (5, 5), layer=10))      # on the big rectangle, pin layer
    top.add(gdstk.Label("stray", (50, 50), layer=10))   # in empty space
    lib.new_cell("scratch")                             # empty + orphan cell
    return lib


def main():
    model = layout.from_gdstk_library(_messy())
    print(issues.to_markdown(lint_layout(model, text_layers={10}), title="gdsqa layout"))


if __name__ == "__main__":
    main()
