"""`instructions status` — pointer state vs lock."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_paths
from agent_toolkit_cli.instructions_adapters import SUPPORTED_HARNESSES
from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
from agent_toolkit_cli.instructions_lock import read_lock


@click.command(help="Pointer state vs lock (present / missing / conflict).")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
)
@click.pass_context
def status_cmd(ctx: click.Context, scope: str) -> None:
    project_root: Path | None = None
    home: Path | None = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()
        canonical = instructions_paths.project_canonical_agents_md(project_root)
    else:
        canonical = instructions_paths.global_canonical_agents_md()

    lock_path = instructions_paths.lock_file_path(scope, project_root)
    lock = read_lock(lock_path)

    wanted: set[str] = set()
    for entry in lock.instructions.values():
        wanted.update(h for h in entry.harnesses if h in SUPPORTED_HARNESSES)

    for harness in sorted(wanted):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError as exc:
            click.echo(f"{harness:14s}  skip      {exc}")
            continue
        if not pointer.exists() and not pointer.is_symlink():
            click.echo(f"{harness:14s}  missing   {pointer}")
        elif pointer.is_symlink() and pointer.resolve() == canonical.resolve():
            click.echo(f"{harness:14s}  ok        {pointer}")
        elif pointer.is_symlink():
            click.echo(f"{harness:14s}  conflict  {pointer} → {pointer.resolve()}")
        else:
            click.echo(f"{harness:14s}  conflict  {pointer} (real file)")
