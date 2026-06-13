"""Per-column info content for SkillGrid headers.

A column "info entry" is the content shown when the user presses `i` while
the cursor is on a cell in that column. The registry maps a column key
(an entry in INTERACTIVE_AGENTS, or a non-agent key such as "state") to a
factory that produces a fresh ColumnInfo at call time.

Factories — not pre-built ColumnInfo objects — so the Standard list
always reflects the current catalog without an import-time snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent_toolkit_cli.skill_agents import AGENTS, get_standard_agents


@dataclass(frozen=True)
class ColumnInfo:
    """Content displayed by ColumnInfoModal for one column."""
    title: str
    lines: list[str]


def _standard_info(context: dict | None = None) -> ColumnInfo:
    # Asset-type-agnostic via context (#351, #361): the instruction and agent
    # grids reuse this registry key with their own names/asset type; names
    # default to the skills set.
    ctx = context or {}
    asset_type = ctx.get("asset_type", "skills")
    harness_names = tuple(ctx.get("names") or get_standard_agents())
    description = [
        f"Covered by the standard convention for {asset_type} ({len(harness_names)}):",
        "",
    ]
    bullets = [
        f"  • {name} — {AGENTS[name].display_name}"
        if name in AGENTS else f"  • {name}"
        for name in harness_names
    ]
    # Caller-supplied trailing lines (#361): e.g. the agents panel's devin
    # project-scope-only note at global scope. Appended after the bullets.
    extra_lines = list(ctx.get("extra_lines") or [])
    # The 🌐 marker block applies to the asset types whose grids render the
    # marker: skills (#188) and agents (#374). Instructions is excluded by
    # design — each scope has its own canonical AGENTS.md, so there is no
    # cross-scope install concept. The block is also contextual: it only
    # makes sense when the focused row IS installed globally, so omit it
    # when the caller says otherwise.
    show_marker = asset_type in ("skills", "agents") and (
        context is None or bool(ctx.get("global_linked", True))
    )
    indicator_note: list[str] = []
    if show_marker:
        indicator_note = ["", "🌐 marker (project scope only):"]
        if asset_type == "skills":
            indicator_note += [
                "  This skill is also installed globally,",
                "  so you may not need it at project scope too.",
            ]
        else:
            # Agents copy stays presence-neutral (#374): per-harness
            # project-vs-global precedence is not asserted.
            indicator_note += ["  This agent is also installed globally."]
    return ColumnInfo(
        # v3.7 full rename (#350): key and title both say "standard". The
        # agents asset type is a single-file slot, not a bundle (#361); the
        # mcps asset type is a shared .mcp.json projection, not a bundle (#398).
        title=(
            "Standard slot (agents)" if asset_type == "agents"
            else "Standard projection (.mcp.json)" if asset_type == "mcps"
            else "Standard bundle"
        ),
        lines=description + bullets + extra_lines + indicator_note,
    )


def _state_info(context: dict | None = None) -> ColumnInfo:
    # Source of truth for badge meaning: _STATE_MARKUP in
    # agent_toolkit_tui/widgets/skill_grid.py (declaration order preserved).
    return ColumnInfo(
        title="State badges",
        lines=[
            "Per-skill working-tree state in this scope.",
            "",
            "• clean — installed and matches the library canonical",
            "• dirty — installed but the on-disk copy diverges from the library",
            "• missing — in the library, not installed in this scope",
            "• copy — installed as a real copy (symlink fallback — e.g. Windows)",
            "• library — in the library, not yet installed in this project "
            "(project scope only — normal pre-install state)",
            "• unlisted — installed in this project but no longer tracked by "
            "the library lock (re-add via `skill doctor -p`)",
        ],
    )


COLUMN_INFO: dict[str, Callable[..., ColumnInfo]] = {
    "standard": _standard_info,
    "state": _state_info,
}


def get_column_info(name: str, *, context: dict | None = None) -> ColumnInfo | None:
    """Return a fresh ColumnInfo for `name`, or None if unregistered.

    `context` is forwarded to the factory. Today only `_standard_info` reads
    it: `asset_type` (skills/instructions/agents — adjusts title and copy),
    `names` (override the harness list, e.g. the per-scope covered set for
    agents), `extra_lines` (caller-supplied trailing lines, e.g. the agents
    panel's devin note), and `global_linked` (skills/agents 🌐 marker block).
    """
    factory = COLUMN_INFO.get(name)
    if factory is None:
        return None
    return factory(context)
