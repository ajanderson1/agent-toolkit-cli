"""`pi-extension uninstall <slug> [-g/-p]` — toggle a projection OFF.

Keeps the store copy (and the global library lock entry). npm -> drop the
packages[] entry."""
from __future__ import annotations

import click

from agent_toolkit_cli import _pi_settings, pi_extension_install
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots
from agent_toolkit_cli.pi_extension_lock import read_lock, remove_entry, write_lock
from agent_toolkit_cli.pi_extension_paths import library_lock_path, lock_file_path


@click.command("uninstall")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def uninstall_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
) -> None:
    """Remove a Pi extension's projection from the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    glob_lock = read_lock(library_lock_path(env={}))
    entry = glob_lock.skills.get(slug)

    if entry is not None and entry.source_type == "npm":
        _pi_settings.remove_package(entry.source, scope=scope, home=home, project=project)
        click.echo(f"uninstalled {slug} (npm) [{scope}]")
        return

    p = pi_extension_install.plan(slug=slug, scope=scope, action="uninstall",
                                  home=home, project=project)
    try:
        pi_extension_install.apply(p, home=home, project=project)
    except pi_extension_install.InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    if scope == "project" and project is not None:
        proj_lock_path = lock_file_path(scope="project", project=project)
        proj_lock = read_lock(proj_lock_path)
        if slug in proj_lock.skills:
            write_lock(proj_lock_path, remove_entry(proj_lock, slug))
    click.echo(f"uninstalled {slug} [{scope}]")
