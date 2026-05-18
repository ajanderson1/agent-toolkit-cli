"""Pure formatter for `agent-toolkit list --report`.

Consumes the same inventory dict the JSON path produces; emits a grouped
human-readable view: harness → scope → kind → asset entries.
"""
from __future__ import annotations

from pathlib import Path

_HARNESSES = ("claude", "codex", "opencode", "pi")
_SCOPES = ("user", "project")
_KINDS = ("skill", "agent", "command", "hook", "plugin", "pi-extension")


def format_report(inventory: dict, *, project_root: Path) -> str:
    lines: list[str] = []
    lines.append("Asset inventory report")
    lines.append("")
    lines.append(f"Toolkit:  {inventory['toolkit_root']}")
    lines.append(f"Project:  {project_root}")
    lines.append("")

    if not inventory.get("assets"):
        lines.append("(no assets discovered)")
        return "\n".join(lines) + "\n"

    # Group cells: harness -> scope -> kind -> [(slug, status, target)]
    groups: dict[str, dict[str, dict[str, list[tuple[str, str, str | None]]]]] = {}
    for asset in inventory["assets"]:
        for cell in asset["cells"]:
            h, s = cell["harness"], cell["scope"]
            (
                groups.setdefault(h, {})
                .setdefault(s, {})
                .setdefault(asset["kind"], [])
                .append((asset["slug"], cell["status"], cell.get("target")))
            )

    for harness in _HARNESSES:
        if harness not in groups:
            continue
        lines.append(harness)
        for scope in _SCOPES:
            if scope not in groups[harness]:
                continue
            lines.append(f"  {scope}")
            present_kinds = groups[harness][scope]
            for kind in _KINDS:
                if kind not in present_kinds:
                    continue
                entries = sorted(present_kinds[kind], key=lambda t: t[0])
                lines.append(f"    {kind}")
                for slug, status, target in entries:
                    if target:
                        lines.append(f"      {slug:<12} {status:<12} {target}")
                    else:
                        lines.append(f"      {slug:<12} {status}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
