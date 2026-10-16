"""Read-only scope-local Instructions inventory, derived from files and pointers."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path, canonical_usable, inspect_pointer
from agent_toolkit_tui.composition import instructions_nonstandard_main

Scope = Literal['global', 'project']


def interactive_harnesses(selection: tuple[str, ...] | None = None, *, scope: Scope = 'project') -> tuple[str, ...]:
    return instructions_nonstandard_main(selection, scope=scope)


@dataclass(frozen=True)
class InstructionCell:
    linked: bool
    conflict: bool


@dataclass
class InstructionRow:
    slug: str
    source: str
    canonical_exists: bool
    cells: dict[tuple[str, str], InstructionCell] = field(default_factory=dict)


def _cell_for(slug: str, harness: str, *, scope: Scope, home: Path | None,
              project: Path | None, _canonical: Path | None = None) -> InstructionCell | None:
    pointer = pointer_path_for(harness, scope=scope, home=home, project=project)
    if pointer is None or (scope == 'project' and project is None):
        return None
    canonical = _canonical if _canonical is not None else instructions_install._resolve_canonical(scope, project)
    state = inspect_pointer(pointer, canonical)
    return InstructionCell(linked=state.linked, conflict=state.conflict)


def pointer_path_for(harness: str, *, scope: Scope, home: Path | None, project: Path | None) -> Path | None:
    try:
        return _pointer_path(harness, scope, project, home)
    except (ValueError, KeyError):
        return None


def build_instruction_rows(*, scope: Scope, home: Path | None, project: Path | None,
                            selection: tuple[str, ...] | None = None) -> list[InstructionRow]:
    if scope == 'project' and project is None:
        return []
    canonical = instructions_install._resolve_canonical(scope, project)
    slots = instructions_install.pointer_slots(scope=scope, project_root=project, home=home)
    occupied = any(
        (s := inspect_pointer(pointer, canonical)).linked or s.conflict
        for pointer in slots.values()
    )
    if not canonical.exists() and not canonical.is_symlink() and not occupied:
        return []
    row = InstructionRow('AGENTS.md', 'AGENTS.md', canonical_usable(canonical))
    for harness in interactive_harnesses(selection, scope=scope):
        cell = _cell_for('AGENTS.md', harness, scope=scope, home=home, project=project, _canonical=canonical)
        if cell is not None:
            row.cells[(harness, scope)] = cell
        if scope == 'project' and home is not None:
            global_cell = _cell_for('AGENTS.md', harness, scope='global', home=home, project=None)
            if global_cell is not None:
                row.cells[(harness, 'global')] = global_cell
    return [row]
