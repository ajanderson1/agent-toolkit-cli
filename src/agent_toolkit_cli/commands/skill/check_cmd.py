"""Explicit revision checks; never update source content."""
import json

import click

from agent_toolkit_cli.skill_update_check import check_skills
from ._common import scope_and_roots


@click.command("check")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def check_cmd(ctx, slugs, global_, project_flag, as_json):
    """Check registered skills' Git upstream revisions without updating files."""
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None, read_only=True)
    rows = check_skills(slugs, scope=scope, home=home, project=project)
    if as_json:
        click.echo(json.dumps(rows))
    elif not rows:
        click.echo("(no registered skills in this scope)")
    else:
        for row in rows:
            label = "upstream revision differs (check before updating)" if row["status"] == "different" else row["status"]
            click.echo(f"{row['slug']}: {label} · checked {row['checked_at']}")
            if row["local_changes"]:
                click.echo("  Local changes present; check preserves them.")
            if row["error"]:
                click.echo(f"  {row['error']}")
    if any(row["status"] == "unknown" for row in rows):
        ctx.exit(1)
