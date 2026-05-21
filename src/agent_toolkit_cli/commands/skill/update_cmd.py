"""skill update subcommand."""
from __future__ import annotations

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock, write_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, lock_file_path

from ._common import scope_and_roots


@click.command("update")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def update_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
) -> None:
    """Fetch + merge upstream for each skill. Surfaces real git conflicts."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    targets = slugs or tuple(sorted(lock.skills))
    had_conflict = False
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_conflict = True
            continue
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )
        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: copy-mode (no .git/) — cannot update; remove and "
                f"re-add to switch to git-managed",
            )
            had_conflict = True
            continue
        ref = entry.ref or "main"
        skill_git.fetch(canonical, env=None)
        try:
            skill_git.merge(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(
                f"{slug}: conflict during merge (resolve in working copy)"
            )
            click.echo(exc.stderr)
            had_conflict = True
            continue
        entry.local_sha = skill_git.head_sha(canonical, env=None)
        entry.upstream_sha = skill_git.remote_head_sha(
            canonical, ref=ref, env=None,
        )
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")
    if had_conflict:
        ctx.exit(1)
