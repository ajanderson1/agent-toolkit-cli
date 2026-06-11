"""Shared helpers for skill subcommands."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.skill_agents import (
    AGENTS,
    resolve_agent_token,
)


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
):
    """Resolve (scope, home, project_root) from flags + context.

    With ``read_only=True`` and neither flag set, fall back to global when
    no ``<cwd>/skills-lock.json`` exists. This matches ``skill add``'s
    global-by-default mental model for the read-only verbs (``list``,
    ``status``). See issue #210.
    """
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / "skills-lock.json").exists():
        return "global", Path.home(), None
    return "project", None, project_root


def validate_agent_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """Resolve deprecated aliases, then raise UsageError on unknown names."""
    resolved = tuple(resolve_agent_token(n) for n in names)
    for n in resolved:
        if n not in AGENTS:
            raise click.UsageError(f"unknown agent: {n}")
    return resolved
