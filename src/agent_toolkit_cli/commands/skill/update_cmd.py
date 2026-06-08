"""skill update subcommand."""
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


def _summary(repo, *, before: str, after: str) -> str:
    """One-line change summary for an update.

    `up to date` when the clone didn't move; otherwise the changed-file count,
    `+ins/-dels` line delta, and the `before→after` short SHAs — so a refresh
    shows what actually changed instead of a bare `updated`.
    """
    if before == after:
        return "up to date"
    files, ins, dels = skill_git.diff_shortstat(
        repo, base=before, head=after, env=None,
    )
    plural = "file" if files == 1 else "files"
    return (
        f"updated · {files} {plural} +{ins}/-{dels} "
        f"({before[:7]}→{after[:7]})"
    )


@click.command("update", epilog="""\
Examples:

\b
  agent-toolkit-cli skill update              # update all skills
  agent-toolkit-cli skill update journal      # update one skill
""")
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
        read_only=True,
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
        # Monorepo entries: pull the parent clone; the symlinked canonical
        # picks up the new content automatically.
        if entry.parent_url is not None:
            if scope != "global":
                click.echo(
                    f"{slug}: monorepo update only supported at global scope"
                )
                had_conflict = True
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
                had_conflict = True
                continue
            skill_git.fetch(parent_dir, env=None)
            ref = skill_git.resolve_ref(entry.ref, parent_dir)
            before = skill_git.head_sha(parent_dir, env=None)
            try:
                skill_git.merge(parent_dir, ref=ref, env=None)
            except skill_git.GitError as exc:
                click.echo(
                    f"{slug}: merge failed in parent clone at {parent_dir}.\n"
                    f"  Resolve conflicts there (or commit/stash your changes), "
                    f"then re-run `agent-toolkit-cli skill update {slug}`."
                )
                click.echo(exc.stderr)
                had_conflict = True
                continue
            after = skill_git.head_sha(parent_dir, env=None)
            # Copy-mode entries need an explicit re-copy because the library
            # canonical is a stale snapshot of the parent's subfolder, not a
            # live symlink.
            if entry.extras.get("materialised") == "copy":
                library_dir = library_skill_path(slug)
                skill_root = parent_dir / entry.skill_path
                if library_dir.exists():
                    shutil.rmtree(library_dir)
                shutil.copytree(skill_root, library_dir)
            entry.upstream_sha = after
            # Backfill the detected ref so status/push/reset (and the next
            # update) read it instead of re-detecting or falling back to main.
            if entry.ref is None:
                entry.ref = ref
            write_lock(lock_path, lock)
            click.echo(
                f"{slug}: {_summary(parent_dir, before=before, after=after)} "
                f"(parent {entry.source} @ {ref})"
            )
            continue
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
        skill_git.fetch(canonical, env=None)
        ref = skill_git.resolve_ref(entry.ref, canonical)
        before = skill_git.head_sha(canonical, env=None)
        try:
            skill_git.merge(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(
                f"{slug}: conflict during merge (resolve in working copy)"
            )
            click.echo(exc.stderr)
            had_conflict = True
            continue
        after = skill_git.head_sha(canonical, env=None)
        entry.local_sha = after
        entry.upstream_sha = skill_git.remote_head_sha(
            canonical, ref=ref, env=None,
        )
        if entry.ref is None:
            entry.ref = ref
        write_lock(lock_path, lock)
        click.echo(f"{slug}: {_summary(canonical, before=before, after=after)}")
    if had_conflict:
        ctx.exit(1)
