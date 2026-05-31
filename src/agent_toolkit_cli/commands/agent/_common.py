"""Shared helpers for the agent command group.

scope_and_roots is parametrised on AGENT_BINDING.lock_filename
(agents-lock.json), mirroring commands/pi_extension/_common.py.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import click

from agent_toolkit_cli._paths_core import AGENT_BINDING

_LOCK_FILENAME = AGENT_BINDING.lock_filename

Scope = Literal["project", "global"]


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None]:
    """Resolve (scope, home, project_root) from CLI flags + context.

    Convention (cross-cutting, verified):
      - READ verbs pass read_only=True so they default to global outside a
        project (no agents-lock.json in cwd). This avoids a confusing
        "lock not found" error when the user runs `agent list` from their
        home directory.
      - WRITE verbs do NOT pass read_only; they default to project scope so
        the consumer project is the implicit target.
    """
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / _LOCK_FILENAME).exists():
        return "global", Path.home(), None
    return "project", None, project_root
