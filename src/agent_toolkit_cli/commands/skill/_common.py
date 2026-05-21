"""Shared helpers for skill subcommands."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.skill_agents import AGENTS, UnknownAgentError


def scope_and_roots(global_: bool, project: bool, ctx_project: Path | None):
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None
    project_root = ctx_project or Path.cwd()
    return "project", None, project_root


def validate_agent_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """Raise UsageError if any name isn't in the AGENTS catalog."""
    for n in names:
        if n not in AGENTS:
            raise click.UsageError(f"unknown agent: {n}")
    return names
