"""Data model for the TUI's instruction tab.

Reads the instructions lock + filesystem to produce InstructionRow records with
per-harness cell state. Mirrors agent_state.py for the instruction asset type.

Key differences from agent_state:
- Manages pointer symlinks to a canonical AGENTS.md file, not copies.
- Cell state includes a `conflict` flag (real file or foreign symlink in slot).
- INTERACTIVE_HARNESSES is the pinned shortlist: claude-code, gemini-cli.
  The `standard` column is rendered separately by the grid as a read-only status
  column (shows canonical_exists), NOT listed here.
- If the lock is empty but the canonical AGENTS.md exists, emit a single
  AGENTS.md row so a fresh user can install pointers from the grid.

Row-universe contract (#360): instructions are the documented by-design
EXCEPTION to the union semantic (canonical statement: skill_state.py
docstring) — this kind has no library concept (the global lock never
feeds the project-scope universe); the universe is the scope lock plus
the fresh-user canonical fallback above.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import instructions_paths
from agent_toolkit_tui.composition import instructions_nonstandard_main
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import read_lock

Scope = Literal["global", "project"]

# Derived shortlist of installable harnesses whose cells the TUI grid renders
# (#351 — derived from the composition, not pinned; the long tail is
# CLI-only). `standard` is informational only and NOT included here.
INTERACTIVE_HARNESSES: tuple[str, ...] = instructions_nonstandard_main()


@dataclass(frozen=True)
class InstructionCell:
    """Per-(scope, harness) pointer state for the single AGENTS.md slug."""

    linked: bool    # pointer symlink exists and resolves to canonical
    conflict: bool  # pointer slot occupied by a real file or foreign symlink


@dataclass
class InstructionRow:
    """One row per slug (today always 'AGENTS.md')."""

    slug: str
    source: str             # always "AGENTS.md"
    canonical_exists: bool  # True when the canonical AGENTS.md exists on disk
    # Key: (harness_name, scope) → InstructionCell
    cells: dict[tuple[str, str], InstructionCell] = field(default_factory=dict)


def _cell_for(
    slug: str,
    harness: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    _canonical: Path | None = None,
) -> InstructionCell | None:
    """Return InstructionCell for a (slug, harness, scope) triple, or None.

    Returns None when:
    - _pointer_path() raises ValueError (scope mismatch, e.g. replit at global).

    Returns InstructionCell with:
    - linked=True  when pointer is a symlink that resolves to the canonical.
    - conflict=True when pointer slot has a real file or foreign symlink.
    - both False   when slot is absent.

    ``_canonical`` is an internal override used by build_instruction_rows to
    avoid re-computing the canonical path for each harness.
    """
    try:
        pointer = _pointer_path(harness, scope, project, home)
    except (ValueError, KeyError):
        # Scope mismatch or unknown harness — not applicable.
        return None

    # Resolve canonical for this scope.
    if _canonical is not None:
        canonical = _canonical
    elif scope == "global":
        canonical = instructions_paths.global_canonical_agents_md()
    else:
        if project is None:
            return None
        canonical = instructions_paths.project_canonical_agents_md(project)

    if pointer.is_symlink():
        try:
            resolved = pointer.resolve()
        except OSError:
            # Dangling symlink — treat as conflict (foreign/broken).
            return InstructionCell(linked=False, conflict=True)
        if resolved == canonical.resolve():
            return InstructionCell(linked=True, conflict=False)
        # Symlink points elsewhere — foreign symlink conflict.
        return InstructionCell(linked=False, conflict=True)

    if pointer.exists():
        # Real file occupying the slot — conflict.
        return InstructionCell(linked=False, conflict=True)

    # Slot is absent.
    return InstructionCell(linked=False, conflict=False)


def build_instruction_rows(
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> list[InstructionRow]:
    """Build InstructionRow list from the instructions lock + filesystem.

    Reads the scope-appropriate lock. For each slug × INTERACTIVE_HARNESSES,
    tests whether the pointer exists and resolves correctly.

    Empty-lock first-run behavior:
    - If the lock is empty but the canonical AGENTS.md exists, emit a single
      AGENTS.md row with canonical_exists=True and all cells unlinked, so a
      fresh user can install pointers from the grid.
    - If neither lock entry nor canonical exists, return no rows.
    """
    # Resolve paths.
    if scope == "global":
        canonical = instructions_paths.global_canonical_agents_md()
        lock_path = instructions_paths.lock_file_path("global", None)
    else:
        if project is None:
            return []
        canonical = instructions_paths.project_canonical_agents_md(project)
        lock_path = instructions_paths.lock_file_path("project", project)

    canonical_exists = canonical.exists()

    # Read lock (returns empty lock if file absent).
    lock = read_lock(lock_path)

    if not lock.instructions:
        # Lock is empty. Emit a row only if canonical exists (fresh-user path).
        if not canonical_exists:
            return []
        row = InstructionRow(
            slug="AGENTS.md",
            source="AGENTS.md",
            canonical_exists=True,
            cells={},
        )
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(
                "AGENTS.md", harness,
                scope=scope, home=home, project=project,
                _canonical=canonical,
            )
            if cell is not None:
                row.cells[(harness, scope)] = cell
        return [row]

    # Lock has entries — build one row per slug.
    rows: list[InstructionRow] = []
    for slug in sorted(lock.instructions):
        entry = lock.instructions[slug]
        cells: dict[tuple[str, str], InstructionCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(
                slug, harness,
                scope=scope, home=home, project=project,
                _canonical=canonical,
            )
            if cell is not None:
                cells[(harness, scope)] = cell
        rows.append(InstructionRow(
            slug=slug,
            source=entry.source,
            canonical_exists=canonical_exists,
            cells=cells,
        ))
    return rows
