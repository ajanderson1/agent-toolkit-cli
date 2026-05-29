"""`pi-extension list` — the unified read-only inventory (spec §5)."""
from __future__ import annotations

import json

import click

from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_inventory import build_inventory


@click.command("list")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    global_: bool,
    project_flag: bool,
    as_json: bool,
) -> None:
    """List every Pi extension the toolkit can see (store-owned, untracked, npm)."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    records = build_inventory(home=home, project=project_root)
    if as_json:
        click.echo(json.dumps([
            {
                "slug": r.slug, "origin": r.origin, "source": r.source,
                "globalLoaded": r.global_loaded, "projectLoaded": r.project_loaded,
            }
            for r in records
        ], indent=2))
        return
    if not records:
        click.echo("no pi extensions found")
        return
    for r in records:
        g = "✔" if r.global_loaded else "☐"
        p = "✔" if r.project_loaded else "☐"
        click.echo(f"{r.slug}\t{g}\t{p}\t{r.origin}\t{r.source}")
