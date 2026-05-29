"""Shared helpers for the pi-extension command group. scope_and_roots is the
skill version parametrized on the pi-extensions lock filename."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli._paths_core import PI_EXTENSION_BINDING

_LOCK_FILENAME = PI_EXTENSION_BINDING.lock_filename


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[str, Path | None, Path | None]:
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
