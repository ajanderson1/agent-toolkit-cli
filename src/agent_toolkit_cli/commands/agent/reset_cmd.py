"""`agent reset <slugs> [-g/-p] [--force]` — force-sync to upstream HEAD.

Discards local commits and uncommitted edits (git fetch + reset --hard).
Requires at least one slug — there is no implicit "reset everything" form
(mirrors pi-extension reset and skill reset).
"""
from __future__ import annotations

import click
from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.agent_lock import read_lock, write_lock, clone_url_from_entry
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.agent_paths import (
    canonical_agent_dir, agent_git_root, registered_agent_paths, refresh_agent_repo, lock_file_path,
)
from agent_toolkit_cli.commands.agent._common import scope_and_roots, scope_banner


@click.command("reset")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--force", is_flag=True,
              help="Reset even if the working tree is dirty.")
@click.pass_context
def reset_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
    force: bool,
) -> None:
    """Force-sync each named agent to upstream HEAD.

    At least one slug must be given. Run `agent list` to see slugs.
    """
    if not slugs:
        raise click.UsageError(
            "agent reset: at least one slug required. "
            "Run `agent list` to see installed agents."
        )

    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    try:
        lock = read_lock(lock_path)
    except FileNotFoundError:
        raise click.ClickException("no agents lock found")

    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))

    had_error = False

    for slug in slugs:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_error = True
            continue

        entry = lock.skills[slug]
        canonical = canonical_agent_dir(slug, scope=scope, home=home, project=project_root)
        try:
            root = agent_git_root(canonical, slug, entry, project=project_root if scope == "project" else None)
            if not force and skill_git.status(root, env=None) == skill_git.GitWorkingTreeStatus.DIRTY:
                click.echo(f"{slug}: dirty — commit, push, or use --force to discard")
                had_error = True
                continue
            paths = registered_agent_paths(root, library=lock if scope == "global" else None,
                                           scoped=lock if scope == "project" else None, project=project_root)
            relative = entry.agent_path or f"{slug}.md"
            paths[slug] = Path(relative).name if root == canonical.resolve() else relative
            target, _chosen = refresh_agent_repo(root, source_url=clone_url_from_entry(entry),
                ref=entry.ref, paths=paths, reset=True, force=force)
        except (InstallError, skill_git.GitError) as exc:
            click.echo(f"{slug}: reset refused: {exc}")
            had_error = True
            continue

        entry.local_sha = skill_git.head_sha(root, env=None)
        entry.upstream_sha = target
        # Reset does not turn an implicit/default request into another ref.
        write_lock(lock_path, lock)
        click.echo(f"{slug}: reset to {(entry.local_sha or '')[:7]}")

    if had_error:
        ctx.exit(1)
