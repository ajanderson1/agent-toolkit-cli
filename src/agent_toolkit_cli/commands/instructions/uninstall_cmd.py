"""`instructions uninstall` — remove our pointers, clear lock entry."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_install


@click.command(help="Remove pointers we own; leave foreign files and symlinks alone.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
    help="Lock scope.",
)
@click.pass_context
def uninstall_cmd(ctx: click.Context, scope: str) -> None:
    project_root = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()

    instructions_install.uninstall(
        scope=scope, project_root=project_root, home=None
    )
    click.echo(f"uninstalled instructions pointers at {scope} scope")
