"""`pi-extension uninstall <slug> [-g/-p]` — toggle a projection OFF.

Keeps the store copy (and the global library lock entry). npm -> drop the
matching packages[] entry. Delegates to pi_extension_ops (#333)."""
from __future__ import annotations

import click

from agent_toolkit_cli import _pi_settings, pi_extension_install, pi_extension_ops
from agent_toolkit_cli.commands.pi_extension._common import scope_and_roots


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
    scope, home, project, _implicit = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    try:
        pi_extension_ops.uninstall(slug=slug, scope=scope, home=home, project=project)
    except (pi_extension_install.InstallError, _pi_settings.PiSettingsError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"uninstalled {slug} [{scope}]")
