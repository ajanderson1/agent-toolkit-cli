"""`pi-extension install <slug> [-g/-p]` — toggle a projection ON.

store-owned -> symlink into Pi's extensions/ dir (lock-after-projection).
npm         -> add the spec to settings.json packages[] (no symlink).
Delegates to pi_extension_ops (#333)."""
from __future__ import annotations

import click

from agent_toolkit_cli import _pi_settings, pi_extension_install, pi_extension_ops
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots


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
    try:
        pi_extension_ops.install(slug=slug, scope=scope, home=home, project=project)
    except (pi_extension_install.InstallError, _pi_settings.PiSettingsError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"installed {slug} [{scope}]")
