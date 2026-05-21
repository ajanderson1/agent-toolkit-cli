"""skill list subcommand."""
from __future__ import annotations

import click

from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import lock_file_path

from ._common import scope_and_roots


@click.command("list")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def list_cmd(ctx: click.Context, global_: bool, project_flag: bool) -> None:
    """List installed skills from the lock file."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    if not lock.skills:
        click.echo("(no skills installed)")
        return
    for slug in sorted(lock.skills):
        e = lock.skills[slug]
        ref = e.ref or "main"
        short = (e.upstream_sha or "")[:7]
        click.echo(f"{slug}\t{e.source}\t{ref}\t{short}")
