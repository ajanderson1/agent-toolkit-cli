"""Shared helpers for the pi-extension command group. scope_and_roots is the
skill version parametrized on the pi-extensions lock filename."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import click

from agent_toolkit_cli._paths_core import PI_EXTENSION_BINDING

_LOCK_FILENAME = PI_EXTENSION_BINDING.lock_filename

Scope = Literal["project", "global"]


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None, bool]:
    """Resolve (scope, home, project_root, implicit) from CLI flags + context.

    ``implicit`` is True iff neither -g nor -p was passed — i.e. the scope was
    inferred from the presence/absence of <cwd>/pi-extensions-lock.json. Read
    verbs use it to decide whether to print a scope reminder (#420, mirrors
    #413).
    """
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False
    if project:
        project_root = ctx_project or Path.cwd()
        return "project", None, project_root, False
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / _LOCK_FILENAME).exists():
        return "global", Path.home(), None, True
    return "project", None, project_root, True


def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Print a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project — the one case (#420, mirrors #413) where the user got no signal
    about which lock was picked. Goes to stdout by default; callers emitting a
    machine stream (``list --json``) pass ``err=True`` to route it to stderr.
    """
    if not (implicit and scope == "project"):
        return
    noun = "pi extension" if count == 1 else "pi extensions"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )
