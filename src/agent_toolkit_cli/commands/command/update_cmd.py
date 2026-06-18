from __future__ import annotations

import shutil
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.command_lock import read_lock, write_lock
from agent_toolkit_cli.command_paths import (
    canonical_command_dir,
    library_root,
    lock_file_path,
)
from agent_toolkit_cli.commands.command._common import scope_and_roots, validate_slug
from agent_toolkit_cli.skill_paths import resolve_existing_parent_clone


def _summary(repo: Path, *, before: str, after: str) -> str:
    if before == after:
        return "up to date"
    files, ins, dels = skill_git.diff_shortstat(repo, base=before, head=after, env=None)
    plural = "file" if files == 1 else "files"
    return f"updated · {files} {plural} +{ins}/-{dels} ({before[:7]}→{after[:7]})"


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
    had_conflict = False
    for s in slugs:
        entry = lock.skills.get(s)
        if entry is None:
            click.echo(f"{s}: not in lock")
            had_conflict = True
            continue

        # Monorepo entries: update the parent clone; the symlinked canonical
        # picks up new content automatically. Copy-mode canonicals are rebuilt.
        if entry.parent_url is not None:
            if scope != "global":
                click.echo(f"{s}: monorepo command updates are global-only; remove and re-add from global scope")
                had_conflict = True
                continue
            owner, repo = entry.source.split("/", 1)
            parent_dir = resolve_existing_parent_clone(
                owner, repo, ref=entry.ref, parent_url=entry.parent_url, env=None,
                root=library_root(),
            )
            if not skill_git.is_git_repo(parent_dir):
                click.echo(f"{s}: parent clone missing or not a git repo at {parent_dir}")
                had_conflict = True
                continue
            ref = skill_git.resolve_ref(entry.ref, parent_dir)
            before = skill_git.head_sha(parent_dir, env=None)
            try:
                skill_git.fetch_ref(parent_dir, ref=ref, env=None)
                skill_git.reset_hard(parent_dir, ref=ref, env=None)
            except skill_git.GitError as exc:
                click.echo(f"{s}: git failed during parent update\n{exc.stderr}")
                had_conflict = True
                continue
            after = skill_git.head_sha(parent_dir, env=None)
            canonical = canonical_command_dir(s, scope=scope, home=home, project=project)
            if canonical.exists() and not canonical.is_symlink():
                # Copy-mode canonical: rebuild from parent subpath.
                command_root = parent_dir / Path(entry.command_path).parent
                if canonical.is_dir():
                    shutil.rmtree(canonical)
                shutil.copytree(command_root, canonical)
            entry.upstream_sha = after
            entry.local_sha = after
            if entry.ref is None:
                entry.ref = ref
            write_lock(path, lock)
            click.echo(f"{s}: {_summary(parent_dir, before=before, after=after)} (parent {entry.source} @ {ref})")
            continue

        canonical = canonical_command_dir(s, scope=scope, home=home, project=project)
        if not skill_git.is_git_repo(canonical):
            click.echo(f"{s}: copy-mode (no .git/) — cannot update; remove and re-add to switch to git-managed")
            had_conflict = True
            continue
        if skill_git.status(canonical, env=None) != skill_git.GitWorkingTreeStatus.CLEAN:
            click.echo(f"{s}: dirty working tree; commit or reset first")
            had_conflict = True
            continue
        ref = skill_git.resolve_ref(entry.ref, canonical)
        before = skill_git.head_sha(canonical, env=None)
        try:
            skill_git.fetch_ref(canonical, ref=ref, env=None)
            skill_git.reset_hard(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(f"{s}: git failed during update\n{exc.stderr}")
            had_conflict = True
            continue
        after = skill_git.head_sha(canonical, env=None)
        entry.local_sha = after
        entry.upstream_sha = skill_git.remote_head_sha(canonical, ref=ref, env=None)
        if entry.ref is None:
            entry.ref = ref
        write_lock(path, lock)
        click.echo(f"{s}: {_summary(canonical, before=before, after=after)}")
    if had_conflict:
        ctx.exit(1)
