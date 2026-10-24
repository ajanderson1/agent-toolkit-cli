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
@click.option("--yes", is_flag=True, help="Confirm physical npm removal (use disable to retain files).")
@click.option("--external", is_flag=True, help="Explicitly remove a shared external npm installation.")
@click.pass_context
def uninstall_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
    yes: bool,
    external: bool,
) -> None:
    """Unlink a Git projection, or remove a native npm installation/declaration."""
    from agent_toolkit_cli.commands.pi_extension.native_cmd import npm_roots, confirm_npm_removal
    from agent_toolkit_cli.pi_npm_lifecycle import npm_source_for, remove_npm
    native_scope, native_home, native_project = npm_roots(ctx, global_, project_flag)
    try:
        source = npm_source_for(slug, scope=native_scope, home=native_home, project=native_project)
        if source is not None:
            confirm_npm_removal(source, scope=native_scope, yes=yes, external=external)
            remove_npm(identity=source, scope=native_scope, home=native_home, project=native_project, external=external)
            click.echo(f"removed scoped npm installation/declaration: {slug} [{native_scope}]; other scopes/global fallback may remain")
            return
    except _pi_settings.PiSettingsError as exc:
        raise click.ClickException(str(exc)) from exc
    scope, home, project, _implicit = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    try:
        pi_extension_ops.uninstall(slug=slug, scope=scope, home=home, project=project)
    except (pi_extension_install.InstallError, _pi_settings.PiSettingsError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"uninstalled {slug} [{scope}]")
