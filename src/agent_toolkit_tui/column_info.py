"""Per-column info content for SkillGrid headers.

A column "info entry" is the content shown when the user presses `i` while
the cursor is on a cell in that column. The registry maps a column key
(an entry in INTERACTIVE_AGENTS, or a non-agent key such as "state") to a
factory that produces a fresh ColumnInfo at call time.

Factories — not pre-built ColumnInfo objects — so the Universal list
always reflects the current catalog without an import-time snapshot.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from agent_toolkit_cli.skill_agents import AGENTS, get_universal_agents


@dataclass(frozen=True)
class ColumnInfo:
    """Content displayed by ColumnInfoModal for one column."""
    title: str
    lines: list[str]


def _universal_info(context: dict | None = None) -> ColumnInfo:
    harness_names = get_universal_agents()
    description = [
        "Toggles link/unlink for every harness whose",
        "skillsDir is `.agents/skills`.",
        "",
        "Included harnesses:",
    ]
    bullets = [
        f"  • {name} — {AGENTS[name].display_name}"
        for name in harness_names
    ]
    # The 🌐 marker block is contextual: it only makes sense when the focused
    # row IS installed globally. Omit it when the caller says otherwise.
    show_marker = context is None or bool(context.get("global_linked", True))
    indicator_note = [
        "",
        "🌐 marker (project scope only):",
        "  This skill is also installed globally,",
        "  so you may not need it at project scope too.",
    ] if show_marker else []
    return ColumnInfo(
        title="Universal bundle",
        lines=description + bullets + indicator_note,
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
    "universal": _universal_info,
    "state": _state_info,
}


def get_column_info(name: str, *, context: dict | None = None) -> ColumnInfo | None:
    """Return a fresh ColumnInfo for `name`, or None if unregistered.

    `context` is forwarded to the factory. Today only `_universal_info` reads
    it (`global_linked` flag).
    """
    factory = COLUMN_INFO.get(name)
    if factory is None:
        return None
    return factory(context)
