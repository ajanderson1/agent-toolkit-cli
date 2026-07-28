from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.command_install import _current_linked_harnesses, _ordered_tokens
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import (
    canonical_command_dir,
    library_root,
    lock_file_path,
    project_store_root,
)
from agent_toolkit_cli.commands.command._common import scope_and_roots


def _canonical_slugs(*, scope: str, home: Path | None, project: Path | None) -> set[str]:
    """Direct child dirs of the active-scope store with a regular COMMAND.md."""
    if scope == "global":
        root = library_root()
    else:
        if project is None:
            return set()
        root = project_store_root(project)
    if not root.is_dir():
        return set()
    out: set[str] = set()
    for child in root.iterdir():
        if not child.is_dir() and not child.is_symlink():
            continue
        cmd = child / "COMMAND.md"
        if cmd.is_file() and not cmd.is_symlink():
            out.add(child.name)
    return out


@click.command("doctor")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def doctor_cmd(ctx, global_, project_flag):
    """Report command library/projection issues (read-only)."""
    scope, home, project, _ = scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    home = home or (Path.home() if scope == "global" else None)
    lock_path = lock_file_path(scope=scope, home=home, project=project)
    lock = read_lock(lock_path)
    slugs = set(lock.skills) | _canonical_slugs(scope=scope, home=home, project=project)
    ok = True
    for slug in sorted(slugs):
        entry = lock.skills.get(slug)
        cmd = canonical_command_dir(slug, scope=scope, home=home, project=project) / "COMMAND.md"
        if not (cmd.is_file() and not cmd.is_symlink()):
            click.echo(f"{slug}: missing COMMAND.md")
            ok = False
        linked = set(
            _ordered_tokens(
                _current_linked_harnesses(slug=slug, scope=scope, home=home, project=project)
            )
        )
        tracked = set(entry.harnesses) if entry is not None else set()
        # Normalize legacy claude-code for comparison display only — do not write.
        tracked = {"standard" if t == "claude-code" else t for t in tracked}
        missing = sorted(tracked - linked)
        untracked = sorted(linked - tracked)
        for token in missing:
            click.echo(f"{slug}: missing projection: {token}")
            ok = False
        for token in untracked:
            click.echo(f"{slug}: untracked projection: {token}")
            ok = False
        if linked and not missing and not untracked and entry is not None:
            click.echo(f"{slug}: linked {', '.join(_ordered_tokens(linked))}")
    if ok:
        click.echo("commands ok")
