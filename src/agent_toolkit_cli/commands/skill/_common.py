"""Shared helpers for skill subcommands."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.skill_agents import AGENTS


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
):
    """Resolve (scope, home, project_root, implicit) from flags + context.

    ``implicit`` is True iff neither ``-g`` nor ``-p`` was passed — i.e. the
    scope was inferred from the presence of ``<cwd>/skills-lock.json`` (or its
    absence). Verbs use it to decide whether to print a scope reminder (#413).

    With ``read_only=True`` and neither flag set, fall back to global when
    no ``<cwd>/skills-lock.json`` exists. This matches ``skill add``'s
    global-by-default mental model for the read-only verbs (``list``,
    ``status``). See issue #210.
    """
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root, False
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / "skills-lock.json").exists():
        return "global", Path.home(), None, True
    return "project", None, project_root, True


def validate_agent_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """Raise UsageError on names not in the catalog."""
    for n in names:
        if n not in AGENTS:
            raise click.UsageError(f"unknown agent: {n}")
    return names
