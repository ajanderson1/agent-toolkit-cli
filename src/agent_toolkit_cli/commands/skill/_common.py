"""Shared helpers for skill subcommands."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import click

from agent_toolkit_cli.skill_agents import AGENTS

Scope = Literal["project", "global"]


def scope_and_roots(
    global_: bool,
    project: bool,
    ctx_project: Path | None,
    *,
    read_only: bool = False,
) -> tuple[Scope, Path | None, Path | None, bool]:
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


def scope_banner(scope, *, implicit, lock_path, count, err=False) -> None:
    """Print a one-line scope reminder on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly (no -g/-p) AND landed on
    project — the one case (#413) where the user got no signal about which
    lock was picked. Goes to stdout by default (so a human sees it inline with
    the verb output); callers emitting a machine stream pass ``err=True`` to
    route it to stderr instead (today only ``list --json``).
    """
    if not (implicit and scope == "project"):
        return
    noun = "skill" if count == 1 else "skills"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g for the global library.",
        err=err,
    )


def monorepo_wrong_scope_msg(slug: str, verb: str) -> str:
    """The monorepo-at-project-scope refusal message, single-sourced (#421).

    A monorepo skill is a global-library entry; `update`/`reset` at project
    scope is refused because `-g` would switch to the global library (a
    different set), not re-scope this project entry. `update_cmd` and
    `reset_cmd` share the wording verbatim except the verb — see #413.
    """
    return (
        f"{slug}: monorepo skill — {verb} it at global scope. "
        f"Note: -g switches to the global library (a different "
        f"set), it does not {verb} this project entry."
    )


def validate_agent_names(names: tuple[str, ...]) -> tuple[str, ...]:
    """Raise UsageError on names not in the catalog."""
    for n in names:
        if n not in AGENTS:
            raise click.UsageError(f"unknown agent: {n}")
    return names
