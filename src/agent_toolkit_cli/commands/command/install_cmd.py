from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import command_install
from agent_toolkit_cli._install_core import InstallError, InstallPlan
from agent_toolkit_cli.command_lock import read_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, library_lock_path
from agent_toolkit_cli.commands.command._common import (
    DEFAULT_COMMAND_HARNESSES,
    default_install_harnesses,
    parse_harness_tokens,
    scope_and_roots,
    validate_slug,
)


@click.command("install")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "--harnesses",
    default=None,
    help="Comma-separated harness names. Default: standard + Pi + Gemini.",
)
@click.option("--migrate-to-central", is_flag=True, help="Migrate verified private backing, preserving the old checkout.")
@click.pass_context
def install_cmd(ctx, slug, global_, project_flag, harnesses, migrate_to_central=False):
    """Project a command into harness command slots."""
    slug = validate_slug(slug)
    scope, home, project, _ = scope_and_roots(
        global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None,
    )
    if migrate_to_central and (scope != "project" or project is None):
        raise click.UsageError("--migrate-to-central requires project scope")
    global_lock = read_lock(library_lock_path())
    if slug not in global_lock.skills and not canonical_command_dir(slug, scope="global").exists():
        raise click.ClickException(f"{slug}: not in the global library; run `command add` first")
    if harnesses is not None:
        targets = parse_harness_tokens(
            harnesses, scope=scope, slug=slug, home=home, project=project,
        )
    else:
        targets = default_install_harnesses(scope)
    if "codex" in targets:
        click.echo("warning: Codex custom prompts are deprecated", err=True)
    # Project materialisation + rollback live in the facade.
    p = InstallPlan(
        slug=slug,
        scope=scope,
        source=None,
        ref=None,
        add_agents=targets,
        remove_agents=(),
    )
    try:
        def apply_install():
            return command_install.apply(p,
                home=home or (Path.home() if scope == "global" else None), project=project)
        if migrate_to_central:
            from agent_toolkit_cli._paths_core import COMMAND_BINDING
            from agent_toolkit_cli.project_backing import migrate
            old, new, result = migrate(COMMAND_BINDING, slug, project, install=apply_install)
            click.echo(f"{slug}: {old} -> {new} (old backing preserved)")
        else:
            result = apply_install()
    except (InstallError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    for path in result.created:
        click.echo(f"  projected {path}")
    click.echo(f"installed {slug} [{scope}]")
