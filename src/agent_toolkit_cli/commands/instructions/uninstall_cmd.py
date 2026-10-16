"""`instructions uninstall` — remove owned scoped pointers, protecting source chains."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import instructions_install


@click.command(help="Remove pointers we own; leave foreign files and symlinks alone.")
@click.option(
    "--scope",
    type=click.Choice(["project", "global"]),
    default="project",
    help="Pointer scope.",
)
@click.pass_context
def uninstall_cmd(ctx: click.Context, scope: str) -> None:
    project_root = None
    home = None
    if scope == "project":
        obj = ctx.find_root().params.get("project_root")
        project_root = obj if obj else Path.cwd()
    else:
        home = Path.home()

    try:
        instructions_install.uninstall(
            scope=scope, project_root=project_root, home=home
        )
    except (OSError, RuntimeError) as exc:
        raise click.ClickException(f'{exc}; inspect status before retrying') from exc
    click.echo(f"uninstalled instructions pointers at {scope} scope")
