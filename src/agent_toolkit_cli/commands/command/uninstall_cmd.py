from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import command_install
from agent_toolkit_cli.commands.command._common import (
    default_uninstall_harnesses,
    parse_harness_tokens,
    scope_and_roots,
    validate_slug,
)


@click.command("uninstall")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--harnesses", default=None)
@click.pass_context
def uninstall_cmd(ctx, slug, global_, project_flag, harnesses):
    """Remove toolkit-owned command projections."""
    slug = validate_slug(slug)
    scope, home, project, _ = scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    home = home or (Path.home() if scope == "global" else None)
    if harnesses:
        targets = parse_harness_tokens(
            harnesses, scope=scope, slug=slug, home=home, project=project,
        )
    else:
        targets = default_uninstall_harnesses(scope)
    removed = command_install.uninstall(
        slug, targets, scope=scope, home=home, project=project,
    )
    for path in removed:
        click.echo(f"  removed {path}")
    click.echo(f"uninstalled {slug} [{scope}]")
