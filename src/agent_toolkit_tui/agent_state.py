"""Data model for the TUI's agent tab.

Reads the agent lock + filesystem to produce AgentRow records with per-harness
cell state. Mirrors skill_state.py for the agent asset type.

Key differences from skill_state:
- The standard projection is the .claude/agents/<slug>.md slot (#361) — a real
  installable file, not a symlink bundle. It renders as the first column.
- No git working-tree state badge (agents are installed files, not git repos per-se).
- Linked = adapter destination exists (adapter.destination(...).exists() or .is_symlink()).
- INTERACTIVE_HARNESSES is derived: standard slot + non-covered main harnesses.

Row-universe contract: union(library lock, scope lock) — canonical statement
in skill_state.py's module docstring (#360). Rows carry a `state`:
`installed` (in the scope lock), `library` (library-only, dim available),
`unlisted` (scope-lock-only, warning). Pre-#362 the CLI never writes a
project lock, so at project scope the union degenerates to library rows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import lock_file_path
from agent_toolkit_tui.composition import agents_nonstandard_main

Scope = Literal["global", "project"]
State = Literal["installed", "library", "unlisted"]

# Rendered columns (#361): the standard slot first, then the non-covered
# main harnesses (derived per scope; the two scopes yield the same set
# today because devin is not a MAIN harness). Cells are still keyed by
# (scope, harness). The long tail is CLI-only.
INTERACTIVE_HARNESSES: tuple[str, ...] = ("standard",) + agents_nonstandard_main("global")


@dataclass(frozen=True)
class AgentCell:
    """Per-(scope, harness) install state for a single agent slug."""

    linked: bool  # adapter destination exists on disk


@dataclass
class AgentRow:
    """One row per slug in union(library lock, scope lock)."""

    slug: str
    source: str
    ref: str
    state: State = "installed"
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
    """Build AgentRow list from union(library lock, scope lock) + filesystem.

    See the module docstring for the row-universe contract (#360).
    """
    from agent_toolkit_cli.agent_paths import library_lock_path

    def _read(path: Path) -> dict:
        # read_lock returns an empty LockFile on FileNotFoundError — no try/except needed.
        return dict(read_lock(path).skills)

    lib_slugs = _read(library_lock_path())
    scope_slugs = _read(lock_file_path(scope=scope, home=home, project=project))
    # At global scope library_lock_path() IS the scope lock — same file.
    # Merge order: the scope-lock entry wins source/ref for slugs in both
    # locks (skill_state.py inverts this — library wins). Unobservable
    # pre-#362: the CLI writes no agent project lock, and at global scope
    # both reads are the same file.
    universe = {**lib_slugs, **scope_slugs}

    rows: list[AgentRow] = []
    for slug in sorted(universe):
        entry = universe[slug]
        if slug in scope_slugs:
            # At global scope the scope lock IS the library lock (same file),
            # so this branch covers every slug and yields "installed".
            state: State = "installed" if slug in lib_slugs else "unlisted"
        else:
            state = "library"
        cells: dict[tuple[str, str], AgentCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(slug, harness, scope=scope, home=home, project=project)
            if cell is not None:
                cells[(harness, scope)] = cell
        rows.append(AgentRow(
            slug=slug,
            source=entry.source,
            ref=entry.ref or "(default)",
            state=state,
            cells=cells,
        ))
    return rows
