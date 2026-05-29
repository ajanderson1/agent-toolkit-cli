"""`pi-extension status` — per-extension origin + loaded state."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_inventory import build_inventory


@click.command("status")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def status_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
) -> None:
    """Show origin and loaded-scope for each pi extension."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    records = build_inventory(home=home, project=project_root)
    if slugs:
        wanted = set(slugs)
        records = [r for r in records if r.slug in wanted]
    for r in records:
        scopes = []
        if r.global_loaded:
            scopes.append("global")
        if r.project_loaded:
            scopes.append("project")
        loaded = ",".join(scopes) if scopes else "-"
        click.echo(f"{r.slug}\t{r.origin}\t{loaded}")
