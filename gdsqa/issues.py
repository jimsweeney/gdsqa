"""Shared issue format.

Every check in gdsqa returns a list of issue dicts of the form
``{"rule": str, "severity": "error" | "warning", "message": str, ...}``. This module renders that list as
JSON and as a Markdown summary grouped by severity, so every report looks the same regardless of which checks
produced it.
"""
from __future__ import annotations
import json


def to_json(issues):
    return json.dumps(issues, indent=2, default=str)


def to_markdown(issues, title="gdsqa"):
    if not issues:
        return f"# {title}\n\nNo issues found."
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] == "warning"]
    lines = [f"# {title}", "", f"{len(errors)} error(s), {len(warnings)} warning(s)"]
    if errors:
        lines += ["", "## Errors"] + [f"- [{i['rule']}] {i['message']}" for i in errors]
    if warnings:
        lines += ["", "## Warnings"] + [f"- [{i['rule']}] {i['message']}" for i in warnings]
    return "\n".join(lines)
