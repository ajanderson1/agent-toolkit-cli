"""Native npm controls. Scope is explicit/default-global, never lock-inferred."""
from pathlib import Path
import json

import click

from agent_toolkit_cli import pi_npm, pi_npm_lifecycle
from agent_toolkit_cli._pi_settings import PiSettingsError


def npm_roots(ctx, global_: bool, project_flag: bool):
    if global_ and project_flag:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    project = (ctx.obj or {}).get("project_root") or Path.cwd()
    return ("project" if project_flag else "global"), Path.home(), project


def _selection_command(name, enabled):
    @click.command(name)
    @click.argument("identity")
    @click.option("-g", "--global", "global_", is_flag=True)
    @click.option("-p", "--project", "project_flag", is_flag=True)
    @click.pass_context
    def command(ctx, identity, global_, project_flag):
        """Change native npm extension selection only; retain installation and other resources."""
        scope, home, project = npm_roots(ctx, global_, project_flag)
        try:
            if enabled is None:
                pi_npm.reset_npm_override(identity=identity, scope=scope, home=home, project=project)
            else:
                pi_npm.set_npm_enabled(identity=identity, enabled=enabled, scope=scope, home=home, project=project)
        except PiSettingsError as exc:
            raise click.ClickException(str(exc)) from exc
        click.echo(f"{name} {identity} [{scope}] — package files retained")
    return command


enable_cmd = _selection_command("enable", True)
disable_cmd = _selection_command("disable", False)
reset_selection_cmd = _selection_command("reset-selection", None)


@click.command("migrate-npm-records")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--apply", is_flag=True, help="Back up and prune legacy npm registrations; default is dry-run.")
@click.pass_context
def migrate_npm_cmd(ctx, global_, project_flag, apply):
    """Retire obsolete npm records without activating or removing packages."""
    scope, home, project = npm_roots(ctx, global_, project_flag)
    try:
        report = pi_npm_lifecycle.migrate_npm_records(scope=scope, home=home, project=project, apply=apply)
    except (PiSettingsError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(json.dumps(report, indent=2))


def confirm_npm_removal(source, *, scope, yes, external):
    click.echo("npm removal now removes the installation and declaration; use disable to retain files.", err=True)
    click.echo("Bundled skills/prompts/themes may also be removed. Another scope or global fallback can remain active.", err=True)
    if not yes:
        click.confirm(f"Remove {source} [{scope}]" + (" including its shared external npm installation" if external else "") + "?", abort=True)
