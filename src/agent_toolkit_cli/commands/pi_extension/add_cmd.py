"""Git source registration, or native scoped npm installation/configuration."""
from __future__ import annotations

import click

from agent_toolkit_cli import pi_extension_add
from agent_toolkit_cli.skill_git import GitError


@click.command("add")
@click.argument("source")
@click.option("--slug", default=None, help="Override the derived Git library slug (not npm identity).")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def add_cmd(ctx, source: str, slug: str | None, global_: bool, project_flag: bool) -> None:
    """Add a Git library source, or install/configure an npm package through Pi.

    Git sources must address a repository root, not a subdirectory. Existing
    unregistered checkouts are registered only if their origin matches SOURCE.
    Git registration does not activate extensions. npm add is native Pi install,
    default global; -p selects project scope. It downloads packages, not records.
    """
    from agent_toolkit_cli.commands.pi_extension.native_cmd import npm_roots
    scope, home, project = npm_roots(ctx, global_, project_flag)
    if project_flag and not source.startswith("npm:"):
        raise click.UsageError("Git library add is global-only; project scope is supported for npm sources")
    if source.startswith("npm:"):
        click.echo("npm add now performs native Pi installation/configuration; no Toolkit registration is created.", err=True)
    try:
        ext_slug = pi_extension_add.add(source=source, slug=slug, env=None, scope=scope, home=home, project=project)
    except (pi_extension_add.AddError, GitError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"added {ext_slug}")
