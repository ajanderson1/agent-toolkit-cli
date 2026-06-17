from __future__ import annotations
import click
from agent_toolkit_cli.command_install import _current_linked_harnesses
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, lock_file_path
from agent_toolkit_cli.commands.command._common import scope_and_roots

@click.command("doctor")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def doctor_cmd(ctx, global_, project_flag):
    """Report command library/projection issues."""
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project))
    ok = True
    for slug in sorted(lock.skills):
        if not (canonical_command_dir(slug, scope=scope, home=home, project=project) / "COMMAND.md").is_file():
            click.echo(f"{slug}: missing COMMAND.md")
            ok = False
        linked = _current_linked_harnesses(slug=slug, scope=scope, home=home, project=project)
        if linked:
            click.echo(f"{slug}: linked {', '.join(linked)}")
    if ok:
        click.echo("commands ok")
