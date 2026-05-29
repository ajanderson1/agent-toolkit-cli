"""`instructions install` — write lock + reconcile filesystem."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_install, instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import PointerConflictError
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.skill_agents import AGENTS


@click.command(help="Install per-harness pointers to AGENTS.md.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
    help="Lock scope. Project default mirrors the spec — pointers are project-rooted.",
)
@click.option(
    "--harness",
    "harnesses",
    multiple=True,
    help="Specific harness(es) to install. Repeat for multiple. "
    "Default: all symlink-verdict harnesses.",
)
@click.pass_context
def install_cmd(ctx: click.Context, scope: str, harnesses: tuple[str, ...]) -> None:
    project_root = _resolve_project_root(ctx, scope)
    targets = list(harnesses) or sorted(SUPPORTED_HARNESSES)

    # Validate every requested harness BEFORE writing the lock.
    for h in targets:
        if h in SUPPORTED_HARNESSES:
            continue
        if h in AGENTS:
            # In catalog but not symlink-verdict → tell them why.
            raise click.ClickException(
                f"{h!r}: this harness is `native` (reads AGENTS.md by default) — "
                "no pointer needed. See harness-matrix.md."
            )
        raise click.ClickException(f"{h!r}: not in the harness catalog")

    # Global-scope pointer slots use {HOME} templates and need a real home;
    # project templates ignore it. Passing None for global silently breaks
    # install, so compute the home explicitly per scope.
    home = None if scope == "project" else Path.home()

    lock_path = instructions_paths.lock_file_path(scope, project_root)
    prior = read_lock(lock_path)
    prior_existed = lock_path.exists()
    existing = prior.instructions.get("AGENTS.md")
    new_harnesses = sorted({*(existing.harnesses if existing else []), *targets})
    new = add_entry(
        prior,
        "AGENTS.md",
        InstructionsLockEntry(
            scope=scope,
            source="AGENTS.md",
            harnesses=new_harnesses,
        ),
    )
    # apply() reads the lock from disk, so the entry must be written first — but
    # if reconcile fails the lock would lie. Write, then roll back on failure so
    # the lock only ever reflects reality.
    write_lock(lock_path, new)
    try:
        plan = instructions_install.apply(
            scope=scope, project_root=project_root, home=home
        )
    except (
        instructions_install.CanonicalMissingError,
        PointerConflictError,
    ) as exc:
        if prior_existed:
            write_lock(lock_path, prior)
        else:
            lock_path.unlink(missing_ok=True)
        raise click.ClickException(str(exc)) from exc

    for act in plan.actions:
        if act.action == "create":
            click.echo(f"created  {act.harness:14s}  {act.pointer}")
        elif act.action == "noop-already-correct":
            click.echo(f"ok       {act.harness:14s}  {act.pointer}")
        elif act.action == "remove":
            click.echo(f"removed  {act.harness:14s}  {act.pointer}")


def _resolve_project_root(ctx: click.Context, scope: str) -> Path | None:
    """For project scope, derive root from the top-level --project-root or cwd."""
    if scope == "global":
        return None
    obj = ctx.find_root().params.get("project_root")
    return obj if obj else Path.cwd()
