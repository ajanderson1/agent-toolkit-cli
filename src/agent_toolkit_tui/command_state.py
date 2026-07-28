"""Data model for TUI command tab."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.command_adapters import get_adapter
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import library_lock_path, lock_file_path
from agent_toolkit_tui.composition import commands_main

Scope = Literal["global", "project"]
State = Literal["installed", "library", "unlisted"]


def interactive_harnesses(
    scope: Scope = "global",
    selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    """Rendered command cells for ``scope`` (Standard first)."""
    return commands_main(scope, selection)


@dataclass(frozen=True)
class CommandCell:
    linked: bool


@dataclass
class CommandRow:
    slug: str
    source: str
    ref: str
    state: State = "installed"
    cells: dict[tuple[str, str], CommandCell] = field(default_factory=dict)


def _cell_for(slug: str, harness_name: str, *, scope: Scope, home: Path | None, project: Path | None) -> CommandCell | None:
    try:
        adapter = get_adapter(harness_name)
        dest = adapter.destination(slug, scope=scope, home=home, project=project)
    except ValueError:
        return None
    # Prefer ownership-aware probe when a canonical COMMAND.md is available.
    from agent_toolkit_cli.command_paths import canonical_command_dir
    try:
        source = canonical_command_dir(slug, scope=scope, home=home, project=project) / "COMMAND.md"
    except ValueError:
        source = None
    if source is not None and source.is_file() and not source.is_symlink() and hasattr(adapter, "is_installed"):
        return CommandCell(adapter.is_installed(slug, source, scope=scope, home=home, project=project))
    return CommandCell(dest.exists() or dest.is_symlink())


def build_command_rows(
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    selection: tuple[str, ...] | None = None,
) -> list[CommandRow]:
    lib = dict(read_lock(library_lock_path()).skills)
    scoped = dict(read_lock(lock_file_path(scope=scope, home=home, project=project)).skills)
    universe = {**scoped, **lib}
    harnesses = interactive_harnesses(scope, selection)
    rows: list[CommandRow] = []
    for slug in sorted(universe):
        entry = universe[slug]
        scoped_entry = scoped.get(slug)
        if scoped_entry is not None and scoped_entry.harnesses:
            state = "installed"
        elif slug in scoped and slug not in lib:
            state = "unlisted"
        elif scoped_entry is not None:
            # Scope entry with no tracked projections → library-like
            state = "library" if not scoped_entry.harnesses else "installed"
        else:
            state = "library"
        cells: dict[tuple[str, str], CommandCell] = {}
        for harness in harnesses:
            cell = _cell_for(slug, harness, scope=scope, home=home, project=project)
            if cell is not None:
                cells[(harness, scope)] = cell
        if scope == "project" and home is not None:
            global_harnesses = interactive_harnesses("global", selection)
            for harness in global_harnesses:
                cell = _cell_for(slug, harness, scope="global", home=home, project=None)
                if cell is not None:
                    cells[(harness, "global")] = cell
        rows.append(CommandRow(slug=slug, source=entry.source, ref=entry.ref or "(default)", state=state, cells=cells))
    return rows
