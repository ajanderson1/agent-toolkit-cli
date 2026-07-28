from __future__ import annotations

import shutil
from pathlib import Path

import click

from agent_toolkit_cli import command_install
from agent_toolkit_cli.command_lock import read_lock, remove_entry, write_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, lock_file_path
from agent_toolkit_cli.commands.command._common import (
    default_uninstall_harnesses,
    scope_and_roots,
    validate_slug,
)


@click.command("remove")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def remove_cmd(ctx, slug, global_, project_flag):
    """Remove a command from the library lock and canonical store."""
    slug = validate_slug(slug)
    scope, home, project, _ = scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    home = home or (Path.home() if scope == "global" else None)
    path = lock_file_path(scope=scope, home=home, project=project)
    lock = read_lock(path)
    entry = lock.skills.get(slug)
    if entry is not None and entry.harnesses:
        targets = entry.harnesses
    else:
        targets = default_uninstall_harnesses(scope)
    command_install.uninstall(slug, targets, scope=scope, home=home, project=project)
    write_lock(path, remove_entry(lock, slug))
    canonical = canonical_command_dir(slug, scope=scope, home=home, project=project)
    if canonical.is_symlink() or canonical.is_file():
        canonical.unlink(missing_ok=True)
    elif canonical.exists():
        shutil.rmtree(canonical)
    click.echo(f"removed {slug} [{scope}]")
