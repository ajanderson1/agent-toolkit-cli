from __future__ import annotations

import shutil
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.command_lock import LockEntry, add_entry, clone_url_from_entry, read_lock, write_lock
from agent_toolkit_cli.command_paths import command_parent_clone_path, library_command_path, library_lock_path


@click.command("import")
@click.argument("file", type=click.Path(path_type=Path), required=False)
@click.option("--latest", is_flag=True, help="Clone at each ref's latest HEAD instead of recorded SHA.")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
def import_cmd(file: Path | None, latest: bool, global_: bool, project_flag: bool):
    """Add commands from another commands-lock.json into the global library."""
    if project_flag:
        raise click.UsageError("command import is global-library only")
    if file is None:
        file = library_lock_path()
    if not file.exists():
        raise click.UsageError(f"import file not found: {file}")
    incoming = read_lock(file)
    current_path = library_lock_path()
    current = read_lock(current_path)
    added: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    for slug, entry in sorted(incoming.skills.items()):
        if slug in current.skills:
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (already present)")
            continue
        canonical = library_command_path(slug)
        if canonical.exists() or canonical.is_symlink():
            skipped.append(slug)
            click.echo(f"  skipped  {slug}  (store copy already exists)")
            continue
        try:
            command_path = entry.command_path or "COMMAND.md"
            source_url = clone_url_from_entry(entry)
            if "/" in command_path:
                parent_url = entry.parent_url or source_url
                parts = Path(command_path).parts
                subpath = str(Path(*parts[:-1]))
                owner, repo = (entry.source.split("/", 1) if "/" in entry.source else ("import", slug))
                parent = command_parent_clone_path(owner, repo, ref=entry.ref)
                parent.parent.mkdir(parents=True, exist_ok=True)
                if not parent.exists():
                    skill_git.clone_pinned_or_branch(parent_url, parent, ref=entry.ref, env=None)
                if entry.upstream_sha and not latest:
                    try:
                        skill_git.fetch_ref(parent, ref=entry.upstream_sha, env=None)
                        skill_git.checkout(parent, ref=entry.upstream_sha, env=None)
                    except skill_git.GitError:
                        pass
                target = parent / subpath
                if not (target / "COMMAND.md").is_file() or (target / "COMMAND.md").is_symlink():
                    raise RuntimeError(f"{command_path} missing or unsafe")
                canonical.parent.mkdir(parents=True, exist_ok=True)
                try:
                    canonical.symlink_to(target, target_is_directory=True)
                except OSError:
                    shutil.copytree(target, canonical)
                repo_for_sha = parent
            else:
                canonical.parent.mkdir(parents=True, exist_ok=True)
                skill_git.clone_pinned_or_branch(source_url, canonical, ref=entry.ref, env=None)
                if entry.upstream_sha and not latest:
                    try:
                        skill_git.fetch_ref(canonical, ref=entry.upstream_sha, env=None)
                        skill_git.checkout(canonical, ref=entry.upstream_sha, env=None)
                    except skill_git.GitError:
                        pass
                if not (canonical / "COMMAND.md").is_file() or (canonical / "COMMAND.md").is_symlink():
                    raise RuntimeError("COMMAND.md missing or unsafe")
                repo_for_sha = canonical
            try:
                upstream = skill_git.remote_head_sha(repo_for_sha, ref=skill_git.resolve_ref(entry.ref, repo_for_sha), env=None)
            except Exception:
                upstream = entry.upstream_sha
            try:
                local = skill_git.head_sha(repo_for_sha, env=None)
            except Exception:
                local = None
            current = add_entry(current, slug, LockEntry(source=entry.source, source_type=entry.source_type, ref=entry.ref, command_path=entry.command_path, upstream_sha=upstream, local_sha=local, parent_url=entry.parent_url, read_only=entry.read_only, extras=dict(entry.extras)))
            write_lock(current_path, current)
            added.append(slug)
            click.echo(f"  added    {slug}  <- {entry.source}")
        except Exception as exc:  # noqa: BLE001
            failed.append((slug, str(exc)))
            if canonical.is_symlink() or canonical.is_file():
                canonical.unlink(missing_ok=True)
            elif canonical.exists():
                shutil.rmtree(canonical, ignore_errors=True)
            click.echo(f"  failed   {slug}  ({exc})")
    click.echo(f"summary: {len(added)} added, {len(skipped)} skipped, {len(failed)} failed")
    if failed:
        raise click.ClickException("one or more commands failed to import")
