from __future__ import annotations
import click
from agent_toolkit_cli import skill_git
from agent_toolkit_cli.command_paths import canonical_command_dir
from agent_toolkit_cli.commands.command._common import scope_and_roots, validate_slug

@click.command("reset")
@click.argument("slug")
@click.option("--force", is_flag=True)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def reset_cmd(ctx, slug, force, global_, project_flag):
    """Discard local command clone changes when --force is provided."""
    slug = validate_slug(slug)
    if not force:
        raise click.ClickException("reset requires --force")
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    canonical = canonical_command_dir(slug, scope=scope, home=home, project=project)
    if skill_git.is_git_repo(canonical):
        skill_git.reset_hard(canonical, ref="HEAD", env=None)
    click.echo(f"reset {slug}")
