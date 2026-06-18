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
@click.option("--force", is_flag=True, help="Remove even if the store copy is dirty.")
def remove_cmd(slug: str, force: bool) -> None:
    """Remove a Pi extension from the global library."""
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
