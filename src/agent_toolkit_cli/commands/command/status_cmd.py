from __future__ import annotations
import click
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, lock_file_path
from agent_toolkit_cli.commands.command._common import scope_and_roots

@click.command("status")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def status_cmd(ctx, global_, project_flag):
    """Show command canonical status."""
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    if not lock.skills:
        click.echo("no commands")
        return
    for slug in sorted(lock.skills):
        state = "present" if (canonical_command_dir(slug, scope=scope, home=home, project=project) / "COMMAND.md").is_file() else "missing-command"
        click.echo(f"{slug}\t{state}")
