"""Command-line entry point for gdsqa.

Three subcommands, by input type:

    python -m gdsqa.cli layout chip.gds [--text-layers 10 11] [--min-chain-depth 3] [-o out]
    python -m gdsqa.cli ports  model.json [-o out]
    python -m gdsqa.cli stack  stack.json [-o out]

`layout` runs the hierarchy and label checks on a GDS file. `ports` runs the port and connection checks on a
JSON model. `stack` runs the LayerStack checks on a JSON level dict. Each writes report.json and report.md and
exits non-zero if any error-severity issue is found, so it works as a CI gate.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

from . import issues, ports, stack, layout, lint_layout


def _write(issue_list, out_dir, title):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "report.json")
    md_path = os.path.join(out_dir, "report.md")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(issues.to_json(issue_list))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(issues.to_markdown(issue_list, title=title))
    n_err = sum(1 for i in issue_list if i["severity"] == "error")
    return {"json": json_path, "markdown": md_path, "n_issues": len(issue_list), "n_errors": n_err}


def run_layout(path, out_dir=".", text_layers=(), min_chain_depth=3):
    if not os.path.exists(path):
        raise SystemExit(f"gdsqa: layout file not found: {path}")
    model = layout.from_gds(path)
    return _write(lint_layout(model, text_layers=text_layers, min_chain_depth=min_chain_depth),
                  out_dir, "gdsqa layout")


def run_ports(path, out_dir="."):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"gdsqa: model file not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"gdsqa: {path} is not valid JSON ({e})")
    for key in ("ports", "bbox"):
        if key not in data:
            raise SystemExit(f"gdsqa: the ports model is missing the required '{key}' key")
    model = ports.from_ports(data["ports"], data["bbox"], data.get("grid", 0.001),
                             data.get("allowed_layers"))
    connections = [tuple(c) for c in data.get("connections", [])]
    return _write(ports.check(model, connections), out_dir, "gdsqa ports")


def run_stack(path, out_dir="."):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"gdsqa: stack file not found: {path}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"gdsqa: {path} is not valid JSON ({e})")
    if "levels" not in data:
        raise SystemExit("gdsqa: the stack file is missing the required 'levels' key")
    s = stack.from_levels(data["levels"])
    allow = [tuple(p) for p in data.get("allow_overlap", [])]
    return _write(stack.check(s, allow_overlap=allow, report_gaps=bool(data.get("report_gaps", False))),
                  out_dir, "gdsqa stack")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gdsqa", description="quality-assurance checks for gdsfactory")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("layout", help="hierarchy + label checks on a GDS file")
    pl.add_argument("file")
    pl.add_argument("-o", "--out", default=".")
    pl.add_argument("--text-layers", type=int, nargs="*", default=[])
    pl.add_argument("--min-chain-depth", type=int, default=3)

    pp = sub.add_parser("ports", help="port + connection checks on a JSON model")
    pp.add_argument("file")
    pp.add_argument("-o", "--out", default=".")

    ps = sub.add_parser("stack", help="LayerStack checks on a JSON level dict")
    ps.add_argument("file")
    ps.add_argument("-o", "--out", default=".")

    args = ap.parse_args(argv)
    if args.cmd == "layout":
        out = run_layout(args.file, args.out, set(args.text_layers), args.min_chain_depth)
    elif args.cmd == "ports":
        out = run_ports(args.file, args.out)
    else:
        out = run_stack(args.file, args.out)
    print(f"wrote {out['markdown']} and {out['json']} "
          f"({out['n_issues']} issue(s), {out['n_errors']} error(s))")
    sys.exit(1 if out["n_errors"] else 0)


if __name__ == "__main__":
    main()
