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
    # Kind-agnostic via context (#351): the instruction grid reuses this
    # registry key with its own names/kind; names default to the skills set.
    ctx = context or {}
    kind = ctx.get("kind", "skills")
    harness_names = tuple(ctx.get("names") or get_standard_agents())
    description = [
        f"Covered by the standard convention for {kind} ({len(harness_names)}):",
        "",
    ]
    bullets = [
        f"  • {name} — {AGENTS[name].display_name}"
        if name in AGENTS else f"  • {name}"
        for name in harness_names
    ]
    # The 🌐 marker block is contextual AND skills-only (instructions has no
    # global-marker concept): it only makes sense when the focused row IS
    # installed globally. Omit it when the caller says otherwise.
    show_marker = kind == "skills" and (
        context is None or bool(ctx.get("global_linked", True))
    )
    indicator_note = [
        "",
        "🌐 marker (project scope only):",
        "  This skill is also installed globally,",
        "  so you may not need it at project scope too.",
    ] if show_marker else []
    return ColumnInfo(
        # v3.7 full rename (#350): key and title both say "standard".
        title="Standard bundle",
        lines=description + bullets + indicator_note,
    )


def _longtail_info(context: dict | None = None) -> ColumnInfo:
    # Names arrive via context — nothing imported from composition, keeping
    # this module kind-agnostic (#351).
    names = tuple((context or {}).get("names", ()))
    expanded = bool((context or {}).get("expanded", False))
    head = "Collapsed non-standard harnesses" if not expanded else "Expanded long tail"
    return ColumnInfo(
        title=f"{head} ({len(names)})",
        lines=[
            "Press space on this column to expand/collapse in place.",
            "Expanded columns are browsed with the arrow keys (no jump-to-column).",
            "",
            *[f"  • {n}" for n in names],
        ],
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
        ],
    )


COLUMN_INFO: dict[str, Callable[..., ColumnInfo]] = {
    "standard": _standard_info,
    "state": _state_info,
    "longtail": _longtail_info,
}


def get_column_info(name: str, *, context: dict | None = None) -> ColumnInfo | None:
    """Return a fresh ColumnInfo for `name`, or None if unregistered.

    `context` is forwarded to the factory. Today only `_standard_info` reads
    it (`global_linked` flag).
    """
    factory = COLUMN_INFO.get(name)
    if factory is None:
        return None
    return factory(context)
