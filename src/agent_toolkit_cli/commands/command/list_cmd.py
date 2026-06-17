from __future__ import annotations
import json
import click
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import lock_file_path
from agent_toolkit_cli.commands.command._common import scope_and_roots

@click.command("list")
@click.option("--json", "json_", is_flag=True)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def list_cmd(ctx, json_, global_, project_flag):
    """List command library entries."""
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    rows = [{"slug": slug, "source": e.source, "ref": e.ref, "upstream_sha": e.upstream_sha, "local_sha": e.local_sha, "scope": scope} for slug, e in sorted(lock.skills.items())]
    if json_:
        click.echo(json.dumps(rows, indent=2))
    else:
        for r in rows:
            click.echo(f"{r['slug']}\t{r['source']}\t{r['ref'] or '(default)'}")
