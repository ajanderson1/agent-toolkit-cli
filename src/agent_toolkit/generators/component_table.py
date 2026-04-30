"""Render the component-summary table embedded in AGENTS.md."""
from __future__ import annotations

from collections import Counter
from typing import Mapping

from agent_toolkit.walker import Asset

_KIND_LABELS = {
    "agent": "Agents",
    "command": "Commands",
    "hook": "Hooks",
    "mcp": "MCPs",
    "plugin": "Plugins",
    "skill": "Skills",
}


def render_component_table(
    assets: list[Asset],
    metadata: Mapping[tuple[str, str], dict],
) -> str:
    counts: Counter[str] = Counter()
    origins: dict[str, Counter[str]] = {}
    for asset in assets:
        counts[asset.kind] += 1
        meta = metadata.get((asset.kind, asset.slug), {})
        origin = (meta.get("spec") or {}).get("origin", "unknown")
        origins.setdefault(asset.kind, Counter())[origin] += 1

    rows = ["| Category | Count | Origin breakdown |", "|---|---|---|"]
    for kind in sorted(counts):
        breakdown_parts = [
            f"{n} {origin}" for origin, n in sorted(origins[kind].items())
        ]
        rows.append(f"| {_KIND_LABELS[kind]} | {counts[kind]} | {' · '.join(breakdown_parts)} |")
    return "\n".join(rows) + "\n"
