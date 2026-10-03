"""Static, non-blocking diagnostics for command templates saved as tags.

This module deliberately does not parse or execute shell syntax. Its findings are
heuristics to help catch common mistakes, not a correctness or safety guarantee.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from safe_mode import command_risks

_REFERENCE = re.compile(r"(?<!!)!(?:([A-Za-z_0-9]+)\[(\d+)\]|(\d+))")
_VARIABLE = re.compile(r"(?<!\\)\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
_RUN_DIRECTIVE = re.compile(r"(?:^|\s)run:(auto|manual|prompt|pause=[^\s]+|continue|stop)(?=\s|$)")


def diagnose_template(
    command: str,
    *,
    current_tag: str,
    commands: Iterable[Mapping[str, object]],
    variables: Iterable[str],
) -> list[str]:
    """Return heuristic warnings; comments are inspected only for runbook directives."""
    rows = list(commands)
    vars_known = set(variables)
    warnings: list[str] = []
    refs = list(_REFERENCE.finditer(command))
    by_global_id = {str(row.get("id")): row for row in rows}

    for match in refs:
        tag, tid, global_id = match.groups()
        if tag:
            row = next((r for r in rows if r.get("tag") == tag and str(r.get("tid")) == tid), None)
            if row is None:
                warning = f"Missing command reference !{tag}[{tid}]"
            else:
                warning = ""
            if warning and warning not in warnings:
                warnings.append(warning)
        elif global_id:
            if global_id not in by_global_id:
                warnings.append(f"Missing command reference !{global_id}")


    for match in _VARIABLE.finditer(command):
        name = match.group(1) or match.group(2)
        if name not in vars_known:
            warning = f"Variable ${name} is not currently defined"
            if warning not in warnings:
                warnings.append(warning)

    comments = "\n".join(str(row.get("comment") or "") for row in rows if row.get("tag") == current_tag)
    directives = _RUN_DIRECTIVE.findall(comments)
    if directives:
        modes = sorted({value for value in directives if value in {"auto", "manual", "prompt"}})
        if "auto" in modes:
            warnings.append("run:auto may execute this step without confirmation in :run")
        elif modes:
            warnings.append(f"Runbook directive(s): {', '.join('run:' + mode for mode in modes)}")

    risks = command_risks(command)
    if risks:
        warnings.append(f"Recognized shell risk(s): {', '.join(risks)}")
    return warnings
