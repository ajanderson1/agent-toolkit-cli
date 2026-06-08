"""Data model for the TUI's agent tab.

Reads the agent lock + filesystem to produce AgentRow records with per-harness
cell state. Mirrors skill_state.py for the agent kind.

Key differences from skill_state:
- No universal-bundle concept (agents are real files, not symlinks to a bundle).
- No git working-tree state badge (agents are installed files, not git repos per-se).
- Linked = adapter destination exists (adapter.destination(...).exists() or .is_symlink()).
- INTERACTIVE_HARNESSES is the pinned shortlist of 4 high-value harnesses.
  general-agent is synthetic (mechanism='none') and is NOT rendered.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import lock_file_path

Scope = Literal["global", "project"]

# Pinned shortlist of installable harnesses whose cells the TUI grid renders
# interactively. general-agent is synthetic (mechanism='none') so it is NOT
# included here. This is the single knob to add/remove interactive columns.
INTERACTIVE_HARNESSES: tuple[str, ...] = (
    "claude-code",
    "cursor",
    "pi",
    "gemini-cli",
)


@dataclass(frozen=True)
class AgentCell:
    """Per-(scope, harness) install state for a single agent slug."""

    linked: bool  # adapter destination exists on disk


@dataclass
class AgentRow:
    """One row per locked agent slug."""

    slug: str
    source: str
    ref: str
    # Key: (scope, harness_name) → AgentCell
    cells: dict[tuple[str, str], AgentCell] = field(default_factory=dict)


def _cell_for(
    slug: str,
    harness_name: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> AgentCell | None:
    """Return AgentCell for a (slug, harness, scope) triple, or None if not applicable.

    Returns None when:
    - get_adapter() raises UnsupportedMechanismError (mechanism='none').
    - adapter.destination() raises ValueError (scope mismatch, e.g. dexto at project).

    Returns AgentCell(linked=True) when the adapter destination exists on disk.
    """
    try:
        adapter = get_adapter(harness_name)
    except UnsupportedMechanismError:
        return None
    try:
        dest = adapter.destination(slug, scope=scope, home=home, project=project)
    except ValueError:
        # Scope mismatch — harness is not installable at this scope.
        return None
    linked = dest.exists() or dest.is_symlink()
    return AgentCell(linked=linked)


def build_agent_rows(
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> list[AgentRow]:
    """Build AgentRow list from the agent lock + filesystem.

    Reads the scope-appropriate agent lock. For each slug × enabled harness
    in INTERACTIVE_HARNESSES, tests whether the adapter destination exists.

    Returns rows sorted by slug.
    """
    try:
        lock_path = lock_file_path(scope=scope, home=home, project=project)
        lock = read_lock(lock_path)
    except FileNotFoundError:
        return []

    rows: list[AgentRow] = []
    for slug in sorted(lock.skills):
        entry = lock.skills[slug]
        cells: dict[tuple[str, str], AgentCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(slug, harness, scope=scope, home=home, project=project)
            if cell is not None:
                cells[(harness, scope)] = cell
        rows.append(AgentRow(
            slug=slug,
            source=entry.source,
            ref=entry.ref or "(default)",
            cells=cells,
        ))
    return rows
