from __future__ import annotations
import click
from agent_toolkit_cli import skill_git
from agent_toolkit_cli.command_lock import read_lock, write_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, lock_file_path
from agent_toolkit_cli.commands.command._common import scope_and_roots, validate_slug

@click.command("update")
@click.argument("slug", required=False)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def update_cmd(ctx, slug, global_, project_flag):
    """Fetch and fast-forward command clones."""
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    path = lock_file_path(scope=scope, home=home, project=project)
    lock = read_lock(path)
    slugs = [validate_slug(slug)] if slug else sorted(lock.skills)
    for s in slugs:
        canonical = canonical_command_dir(s, scope=scope, home=home, project=project)
        if skill_git.is_git_repo(canonical):
            if skill_git.status(canonical, env=None) != skill_git.GitWorkingTreeStatus.CLEAN:
                raise click.ClickException(f"{s}: dirty working tree; commit or reset first")
            ref = skill_git.resolve_ref(lock.skills.get(s).ref if s in lock.skills else None, canonical)
            skill_git.fetch_ref(canonical, ref=ref, env=None)
            skill_git.reset_hard(canonical, ref=ref, env=None)
        click.echo(f"updated {s}")
    write_lock(path, lock)
