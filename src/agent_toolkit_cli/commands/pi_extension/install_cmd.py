"""`pi-extension install <slug> [-g/-p]` — toggle a projection ON.

store-owned -> symlink into Pi's extensions/ dir (lock-after-projection).
npm         -> add the spec to settings.json packages[] (no symlink).
"""
from __future__ import annotations

import click

from agent_toolkit_cli import _pi_settings, pi_extension_install
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_lock import (
    LockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.pi_extension_paths import library_lock_path, lock_file_path


@click.command("install")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def install_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
) -> None:
    """Project a Pi extension into the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    glob_lock = read_lock(library_lock_path(env={}))
    entry = glob_lock.skills.get(slug)
    if entry is None:
        raise click.ClickException(
            f"{slug}: not in the global library; run `pi-extension add` first"
        )

    if entry.source_type == "npm":
        _pi_settings.add_package(entry.source, scope=scope, home=home, project=project)
        click.echo(f"installed {slug} (npm) [{scope}]")
        return

    # store-owned: project the symlink FIRST, then record project lock state.
    p = pi_extension_install.plan(slug=slug, scope=scope, action="install",
                                  home=home, project=project)
    try:
        pi_extension_install.apply(p, home=home, project=project)
    except pi_extension_install.InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug not in proj_lock.skills:
            write_lock(proj_lock_path, add_entry(proj_lock, slug, LockEntry(
                source=entry.source, source_type=entry.source_type,
                ref=entry.ref, pi_extension_path=entry.pi_extension_path,
            )))
    click.echo(f"installed {slug} [{scope}]")
