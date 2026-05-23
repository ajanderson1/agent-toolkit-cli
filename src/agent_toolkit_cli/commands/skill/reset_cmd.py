"""skill reset subcommand — force-sync to upstream HEAD."""
from __future__ import annotations

import shutil

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    library_skill_path,
    lock_file_path,
    parent_clone_path,
)

from ._common import scope_and_roots


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
    """Force-sync each named skill to upstream HEAD.

    Runs `git fetch` + `git reset --hard origin/<ref>` in the library clone
    for each slug, discarding local commits and uncommitted edits. Refuses
    to operate on a dirty working tree unless --force is given (mirrors
    `skill remove --force`). After a successful reset, updates the lock
    entry's `local_sha` and `upstream_sha`.

    At least one slug must be given — there is intentionally no implicit
    "reset everything" form. Run `skill list` to see installed slugs.
    """
    if not slugs:
        raise click.UsageError(
            "skill reset: at least one slug required. "
            "Run `skill list` to see installed skills."
        )

    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)

    had_error = False
    for slug in slugs:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_error = True
            continue

        entry = lock.skills[slug]

        if entry.parent_url is not None:
            if scope != "global":
                click.echo(
                    f"{slug}: monorepo reset only supported at global scope"
                )
                had_error = True
                continue
            owner, repo = entry.source.split("/", 1)
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
            )
            if not skill_git.is_git_repo(parent_dir):
                click.echo(
                    f"{slug}: parent clone missing or not a git repo at "
                    f"{parent_dir}"
                )
                had_error = True
                continue
            if not force:
                wt = skill_git.status(parent_dir, env=None)
                if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                    click.echo(
                        f"{slug}: parent clone at {parent_dir} is dirty — "
                        f"commit, push, or use --force to discard"
                    )
                    had_error = True
                    continue
            ref = entry.ref or "main"
            try:
                skill_git.fetch(parent_dir, env=None)
                skill_git.reset_hard(parent_dir, ref=ref, env=None)
            except skill_git.GitError as exc:
                raise click.ClickException(
                    f"{slug}: git failed during parent reset\n{exc.stderr}"
                ) from exc
            if entry.extras.get("materialised") == "copy":
                library_dir = library_skill_path(slug)
                skill_root = parent_dir / entry.skill_path
                if library_dir.exists():
                    shutil.rmtree(library_dir)
                shutil.copytree(skill_root, library_dir)
            entry.upstream_sha = skill_git.head_sha(parent_dir, env=None)
            write_lock(lock_path, lock)
            click.echo(
                f"{slug}: reset parent {entry.source} to "
                f"{entry.upstream_sha[:7]}"
            )
            continue

        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )

        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: copy-mode (no .git/) — cannot reset; remove "
                f"and re-add to switch to git-managed",
            )
            had_error = True
            continue

        if not force:
            wt = skill_git.status(canonical, env=None)
            if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                click.echo(
                    f"{slug}: dirty — commit, push, or use --force to discard"
                )
                had_error = True
                continue

        ref = entry.ref or "main"
        try:
            skill_git.fetch(canonical, env=None)
            skill_git.reset_hard(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            raise click.ClickException(
                f"{slug}: git failed during reset\n{exc.stderr}"
            ) from exc

        entry.local_sha = skill_git.head_sha(canonical, env=None)
        entry.upstream_sha = skill_git.remote_head_sha(
            canonical, ref=ref, env=None,
        )
        write_lock(lock_path, lock)
        click.echo(f"{slug}: reset to {entry.local_sha[:7]}")

    if had_error:
        ctx.exit(1)
