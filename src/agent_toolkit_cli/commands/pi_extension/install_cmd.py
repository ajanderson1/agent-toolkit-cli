"""Link a Git library source, or delegate scoped npm installation to native Pi."""
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
    """Link a Git library extension, or perform native npm installation (default global)."""
    from agent_toolkit_cli.commands.pi_extension.native_cmd import npm_roots
    from agent_toolkit_cli.pi_npm_lifecycle import npm_source_for, install_npm
    native_scope, native_home, native_project = npm_roots(ctx, global_, project_flag)
    try:
        source = npm_source_for(slug, scope=native_scope, home=native_home, project=native_project)
        if source is not None:
            install_npm(source=source, scope=native_scope, home=native_home, project=native_project)
            click.echo(f"installed {slug} [{native_scope}] through Pi")
            return
    except _pi_settings.PiSettingsError as exc:
        raise click.ClickException(str(exc)) from exc
    scope, home, project, _implicit = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    try:
        pi_extension_ops.install(slug=slug, scope=scope, home=home, project=project)
    except (pi_extension_install.InstallError, _pi_settings.PiSettingsError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"installed {slug} [{scope}]")
