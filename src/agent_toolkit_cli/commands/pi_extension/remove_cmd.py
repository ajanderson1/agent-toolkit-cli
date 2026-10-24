"""`pi-extension remove <slug>` — drop the store copy + global lock entry.

Dirty-guard: refuse if the store copy has uncommitted git changes unless
--force. npm rows: just drop the lock entry (nothing stored)."""
from __future__ import annotations

import shutil

import click


from agent_toolkit_cli.pi_extension_ops import unmanaged_npm_advice
from pathlib import Path
from agent_toolkit_cli import skill_git
from agent_toolkit_cli.pi_extension_lock import read_lock, remove_entry, write_lock
from agent_toolkit_cli.pi_extension_paths import library_lock_path, library_pi_extension_path


@click.command("remove")
@click.argument("slug")
@click.option("--force", is_flag=True, help="Remove even if the Git store copy is dirty.")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--yes", is_flag=True, help="Confirm physical npm removal.")
@click.option("--external", is_flag=True, help="Explicitly remove a shared external npm installation.")
@click.pass_context
def remove_cmd(ctx, slug: str, force: bool, global_: bool, project_flag: bool, yes: bool, external: bool) -> None:
    """Remove a Git library source, or a scoped native npm installation/declaration."""
    from agent_toolkit_cli.commands.pi_extension.native_cmd import npm_roots, confirm_npm_removal
    from agent_toolkit_cli.pi_npm_lifecycle import npm_source_for, remove_npm
    from agent_toolkit_cli._pi_settings import PiSettingsError
    scope, home, project = npm_roots(ctx, global_, project_flag)
    try:
        source = npm_source_for(slug, scope=scope, home=home, project=project)
        if source is not None:
            confirm_npm_removal(source, scope=scope, yes=yes, external=external)
            remove_npm(identity=source, scope=scope, home=home, project=project, external=external)
            click.echo(f"removed scoped npm installation/declaration: {slug} [{scope}]; other scopes/global fallback may remain")
            return
    except PiSettingsError as exc:
        raise click.ClickException(str(exc)) from exc
    if project_flag:
        raise click.UsageError("Git library removal is global-only")
    lock_path = library_lock_path(env={})
    lock = read_lock(lock_path)
    entry = lock.skills.get(slug)
    if entry is None:
        advice = unmanaged_npm_advice(slug, scope="project", home=Path.home(), project=Path.cwd(), action="remove")
        if advice:
            raise click.ClickException(advice)
        advice = unmanaged_npm_advice(slug, scope="global", home=Path.home(), project=Path.cwd(), action="remove")
        if advice:
            raise click.ClickException(advice)
        raise click.ClickException(f"{slug}: not in the global library")

    if entry.source_type != "npm":
        canonical = library_pi_extension_path(slug, env={})
        if canonical.exists() and skill_git.is_git_repo(canonical):
            if (
                skill_git.status(canonical, env=None)
                == skill_git.GitWorkingTreeStatus.DIRTY
                and not force
            ):
                raise click.ClickException(
                    f"{slug}: store copy has uncommitted changes; "
                    f"push/commit them or re-run with --force"
                )
        if canonical.exists():
            shutil.rmtree(canonical)

    write_lock(lock_path, remove_entry(lock, slug))
    click.echo(f"removed {slug}")
