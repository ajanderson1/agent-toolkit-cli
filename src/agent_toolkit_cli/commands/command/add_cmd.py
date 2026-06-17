from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.command_lock import LockEntry, add_entry, read_lock, write_lock
from agent_toolkit_cli.command_paths import command_parent_clone_path, library_command_path, library_lock_path
from agent_toolkit_cli.commands.command._common import validate_slug
from agent_toolkit_cli.skill_source import SourceParseError, parse_source, sanitize_ref


def _derive_slug(parsed) -> str | None:
    if parsed.subpath:
        return Path(parsed.subpath).name
    if parsed.owner_repo:
        return parsed.owner_repo.split("/", 1)[1]
    return Path(parsed.url).name or None


def _sha(canonical: Path, ref: str | None) -> tuple[str | None, str | None]:
    if not skill_git.is_git_repo(canonical):
        return None, None
    try:
        upstream = skill_git.remote_head_sha(canonical, ref=skill_git.resolve_ref(ref, canonical), env=None)
    except Exception:
        upstream = None
    try:
        local = skill_git.head_sha(canonical, env=None)
    except Exception:
        local = None
    return upstream, local


@click.command("add")
@click.argument("source")
@click.option("--slug", default=None, help="Override derived slug.")
@click.option("--ref", default=None, help="Branch, tag, or SHA to clone.")
def add_cmd(source: str, slug: str | None, ref: str | None) -> None:
    """Add a command to the global library."""
    try:
        parsed = parse_source(source)
        if ref is not None:
            ref = sanitize_ref(ref)
            parsed = dataclasses.replace(parsed, ref=ref)
    except SourceParseError as exc:
        raise click.ClickException(str(exc)) from exc
    final_slug = validate_slug(slug or _derive_slug(parsed) or "")
    if parsed.subpath:
        _add_monorepo(parsed, final_slug)
    else:
        _add_single(parsed, final_slug)


def _add_single(parsed, final_slug: str) -> None:
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    requested = parsed.owner_repo or parsed.url
    existing = lock.skills.get(final_slug)
    if existing is not None:
        if existing.source != requested:
            raise click.ClickException(f"{final_slug}: library entry exists with source {existing.source!r}; refusing to overwrite with {requested!r}. Run `command remove {final_slug}` first.")
        click.echo(f"already in library: {final_slug}")
        return
    canonical = library_command_path(final_slug)
    fresh = False
    if not canonical.exists():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone_pinned_or_branch(parsed.url, canonical, ref=parsed.ref, env=None)
            fresh = True
        except skill_git.GitError as exc:
            raise click.ClickException(f"clone failed: {exc}") from exc
    content = canonical / "COMMAND.md"
    if content.is_symlink() or not content.is_file():
        if fresh:
            shutil.rmtree(canonical, ignore_errors=True)
        raise click.ClickException(f"{final_slug}: COMMAND.md absent in source {parsed.url!r}; expected COMMAND.md at the repo root.")
    upstream, local = _sha(canonical, parsed.ref)
    entry = LockEntry(source=requested, source_type=parsed.type, ref=parsed.ref, command_path="COMMAND.md", upstream_sha=upstream, local_sha=local)
    write_lock(lock_path, add_entry(lock, final_slug, entry))
    click.echo(f"added {final_slug} to library <- {parsed.url}")


def _add_monorepo(parsed, final_slug: str) -> None:
    if parsed.owner_repo is None or parsed.subpath is None:
        raise click.UsageError("monorepo source must resolve to owner/repo/subpath")
    owner, repo = parsed.owner_repo.split("/", 1)
    parent = command_parent_clone_path(owner, repo, ref=parsed.ref)
    if not parent.exists():
        parent.parent.mkdir(parents=True, exist_ok=True)
        try:
            skill_git.clone_pinned_or_branch(parsed.url, parent, ref=parsed.ref, env=None)
        except skill_git.GitError as exc:
            raise click.ClickException(f"parent clone failed: {exc}") from exc
    command_root = parent / parsed.subpath
    content = command_root / "COMMAND.md"
    if content.is_symlink() or not content.is_file():
        raise click.ClickException(f"{final_slug}: COMMAND.md not found at {parsed.subpath}/COMMAND.md in {parsed.owner_repo}")
    command_path = f"{parsed.subpath}/COMMAND.md"
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    existing = lock.skills.get(final_slug)
    if existing is not None:
        if existing.source != parsed.owner_repo or existing.command_path != command_path:
            raise click.ClickException(f"{final_slug}: library entry exists; refusing to overwrite. Run `command remove {final_slug}` first.")
        click.echo(f"already in library: {final_slug}")
        return
    canonical = library_command_path(final_slug)
    if not canonical.exists() and not canonical.is_symlink():
        canonical.parent.mkdir(parents=True, exist_ok=True)
        try:
            canonical.symlink_to(command_root, target_is_directory=True)
        except OSError:
            shutil.copytree(command_root, canonical)
    try:
        upstream = skill_git.remote_head_sha(parent, ref=skill_git.resolve_ref(parsed.ref, parent), env=None)
        local = skill_git.head_sha(parent, env=None)
    except Exception:
        upstream = local = None
    entry = LockEntry(source=parsed.owner_repo, source_type=parsed.type, ref=parsed.ref, command_path=command_path, upstream_sha=upstream, local_sha=local, parent_url=parsed.url, read_only=True)
    write_lock(lock_path, add_entry(lock, final_slug, entry))
    click.echo(f"added {final_slug} to library <- {parsed.url}/{parsed.subpath}")
