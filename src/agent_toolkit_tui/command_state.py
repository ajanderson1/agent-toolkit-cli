"""Data model for TUI command tab."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.command_adapters import DEFAULT_HARNESSES, SUPPORTED_HARNESSES, get_adapter
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import library_lock_path, lock_file_path

Scope = Literal["global", "project"]
State = Literal["installed", "library", "unlisted"]
INTERACTIVE_HARNESSES = DEFAULT_HARNESSES


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
        dest = get_adapter(harness_name).destination(slug, scope=scope, home=home, project=project)
    except ValueError:
        return None
    return CommandCell(dest.exists() or dest.is_symlink())


def build_command_rows(*, scope: Scope, home: Path | None, project: Path | None) -> list[CommandRow]:
    lib = dict(read_lock(library_lock_path()).skills)
    scoped = dict(read_lock(lock_file_path(scope=scope, home=home, project=project)).skills)
    universe = {**scoped, **lib}
    rows: list[CommandRow] = []
    for slug in sorted(universe):
        entry = universe[slug]
        state: State = "installed" if slug in scoped else "library"
        if slug in scoped and slug not in lib:
            state = "unlisted"
        cells: dict[tuple[str, str], CommandCell] = {}
        for harness in INTERACTIVE_HARNESSES:
            cell = _cell_for(slug, harness, scope=scope, home=home, project=project)
            if cell is not None:
                cells[(harness, scope)] = cell
        if scope == "project" and home is not None:
            for harness in INTERACTIVE_HARNESSES:
                cell = _cell_for(slug, harness, scope="global", home=home, project=None)
                if cell is not None:
                    cells[(harness, "global")] = cell
        rows.append(CommandRow(slug=slug, source=entry.source, ref=entry.ref or "(default)", state=state, cells=cells))
    return rows
