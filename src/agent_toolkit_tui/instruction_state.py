"""Data model for the TUI's instruction tab.

Reads the instructions lock + filesystem to produce InstructionRow records
with per-harness cell state. Mirrors agent_state.py for the instruction kind.

Key differences from agent_state:
- The instruction kind has a single logical slug per scope ("AGENTS.md").
- Cells are keyed by harness name only (scope is captured in the row).
- applicable=False when the harness has no slot for the scope
  (e.g. replit at global) — caught via try/except ValueError from
  symlink._pointer_path, mirroring agent_state._cell_for.
- linked=True iff the pointer .is_symlink() and .resolve() == canonical.resolve().
- INTERACTIVE_HARNESSES is the pinned shortlist of 2 harnesses rendered in
  the TUI. This is the single knob to add/remove interactive columns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import read_lock

Scope = Literal["global", "project"]

# Pinned shortlist of harnesses whose cells the TUI grid renders interactively.
# These are the two most common harnesses with distinct pointer files.
INTERACTIVE_HARNESSES: tuple[str, ...] = ("claude-code", "gemini-cli")


@dataclass
class InstructionCell:
    """Per-harness install state for the instruction slug at a given scope."""

    applicable: bool  # False when harness has no slot for this scope
    linked: bool      # True iff the pointer is_symlink() and resolves to canonical


@dataclass
class InstructionRow:
    """One row per scope that has a lock entry (global / project)."""

    slug: str                          # always "AGENTS.md" for now
    scope: Scope
    general_linked: bool               # canonical AGENTS.md exists at this scope
    cells: dict[str, InstructionCell] = field(default_factory=dict)


def _cell_for_harness(
    harness: str,
    *,
    scope: Scope,
    canonical: Path,
    home: Path | None,
    project: Path | None,
) -> InstructionCell:
    """Return InstructionCell for a (harness, scope) pair.

    Returns InstructionCell(applicable=False, linked=False) when the harness
    has no slot for the requested scope (symlink._pointer_path raises ValueError).
    """
    try:
        pointer = _pointer_path(harness, scope, project, home)
    except ValueError:
        # Scope mismatch — harness has no slot at this scope (e.g. replit @ global).
        return InstructionCell(applicable=False, linked=False)

    if pointer.is_symlink():
        try:
            linked = pointer.resolve() == canonical.resolve()
        except OSError:
            linked = False
    else:
        linked = False

    return InstructionCell(applicable=True, linked=linked)


def _canonical_for_scope(scope: Scope, *, home: Path | None, project: Path | None) -> Path:
    """Return the canonical AGENTS.md path for the given scope.

    When `home` is explicitly provided, use it directly to construct the global
    canonical path (test-friendly: avoids relying on Path.home() / $HOME).
    """
    if scope == "global":
        if home is not None:
            # Derive global canonical directly from the supplied home path.
            return home / ".agent-toolkit" / "AGENTS.md"
        return instructions_paths.global_canonical_agents_md()
    if project is None:
        raise ValueError("project scope requires project= to be set")
    return instructions_paths.project_canonical_agents_md(project)


def build_instruction_rows(
    *,
    home: Path | None,
    project: Path | None,
) -> list[InstructionRow]:
    """Build InstructionRow list from the instructions lock + filesystem.

    One row per scope that has a lock entry (global and/or project). Reads the
    appropriate instructions-lock.json for each scope. Builds cells for each
    harness in INTERACTIVE_HARNESSES.

    Returns rows ordered global-first, then project.
    """
    rows: list[InstructionRow] = []

    for scope in ("global", "project"):
        # Skip project scope if no project root given.
        if scope == "project" and project is None:
            continue

        try:
            if scope == "global" and home is not None:
                # Use home directly to avoid Path.home() dependency in tests.
                lock_path = home / ".agent-toolkit" / "instructions-lock.json"
            else:
                lock_path = instructions_paths.lock_file_path(scope, project)
        except ValueError:
            continue

        lock = read_lock(lock_path)
        if not lock.instructions:
            continue

        try:
            canonical = _canonical_for_scope(scope, home=home, project=project)
        except ValueError:
            continue

        general_linked = canonical.exists()

        cells: dict[str, InstructionCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cells[harness] = _cell_for_harness(
                harness,
                scope=scope,  # type: ignore[arg-type]
                canonical=canonical,
                home=home,
                project=project,
            )

        rows.append(InstructionRow(
            slug="AGENTS.md",
            scope=scope,  # type: ignore[assignment]
            general_linked=general_linked,
            cells=cells,
        ))

    return rows
