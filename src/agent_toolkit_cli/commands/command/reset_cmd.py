from __future__ import annotations

import shutil
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.command_lock import read_lock, write_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, library_root, lock_file_path
from agent_toolkit_cli.commands.command._common import scope_and_roots, validate_slug
from agent_toolkit_cli.skill_paths import resolve_existing_parent_clone


@click.command("reset")
@click.argument("slug")
@click.option("--force", is_flag=True)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def reset_cmd(ctx, slug, force, global_, project_flag):
    """Discard local command clone changes when --force is provided."""
    slug = validate_slug(slug)
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    path = lock_file_path(scope=scope, home=home, project=project)
    lock = read_lock(path)
    entry = lock.skills.get(slug)
    if entry is None:
        raise click.ClickException(f"{slug}: not in lock")

    if not force:
        raise click.ClickException("reset requires --force")

    # Monorepo entries: reset the parent clone; the symlinked canonical
    # picks up new content automatically. Copy-mode canonicals are rebuilt.
    if entry.parent_url is not None:
        if scope != "global":
            raise click.ClickException(
                f"{slug}: monorepo command resets are global-only; remove and re-add from global scope"
            )
        owner, repo = entry.source.split("/", 1)
        parent_dir = resolve_existing_parent_clone(
            owner, repo, ref=entry.ref, parent_url=entry.parent_url, env=None,
            root=library_root(),
        )
        if not skill_git.is_git_repo(parent_dir):
            raise click.ClickException(f"{slug}: parent clone missing or not a git repo at {parent_dir}")
        ref = skill_git.resolve_ref(entry.ref, parent_dir)
        try:
            skill_git.fetch_ref(parent_dir, ref=ref, env=None)
            skill_git.reset_hard(parent_dir, ref=ref, env=None)
        except skill_git.GitError as exc:
            raise click.ClickException(f"{slug}: git failed during parent reset\n{exc.stderr}") from exc
        canonical = canonical_command_dir(slug, scope=scope, home=home, project=project)
        if canonical.exists() and not canonical.is_symlink():
            command_root = parent_dir / Path(entry.command_path).parent
            if canonical.is_dir():
                shutil.rmtree(canonical)
            shutil.copytree(command_root, canonical)
        entry.upstream_sha = skill_git.head_sha(parent_dir, env=None)
        entry.local_sha = entry.upstream_sha
        if entry.ref is None:
            entry.ref = ref
        write_lock(path, lock)
        click.echo(f"{slug}: reset parent {entry.source} to {entry.upstream_sha[:7]}")
        return

    canonical = canonical_command_dir(slug, scope=scope, home=home, project=project)
    if not skill_git.is_git_repo(canonical):
        raise click.ClickException(f"{slug}: copy-mode (no .git/) — cannot reset; remove and re-add to switch to git-managed")

    ref = skill_git.resolve_ref(entry.ref, canonical)
    try:
        skill_git.fetch_ref(canonical, ref=ref, env=None)
        skill_git.reset_hard(canonical, ref=ref, env=None)
    except skill_git.GitError as exc:
        raise click.ClickException(f"{slug}: git failed during reset\n{exc.stderr}") from exc
    entry.local_sha = skill_git.head_sha(canonical, env=None)
    entry.upstream_sha = skill_git.remote_head_sha(canonical, ref=ref, env=None)
    if entry.ref is None:
        entry.ref = ref
    write_lock(path, lock)
    click.echo(f"{slug}: reset to {entry.local_sha[:7]}")
