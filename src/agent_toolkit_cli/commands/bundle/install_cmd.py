"""`bundle install <ref> [--global/--project]`."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import bundle_install
from agent_toolkit_cli._paths_core import default_scope  # F3 shared helper
from agent_toolkit_cli.bundle_manifest import ManifestError, load


@click.command(help="Install every member of a bundle manifest (all-or-nothing).")
@click.argument("ref", type=click.Path(path_type=Path))
@click.option("--global", "global_", is_flag=True, help="Install all members globally.")
@click.option("--project", "project_", is_flag=True, help="Install all members at project scope.")
def install_cmd(ref: Path, global_: bool, project_: bool) -> None:
    if global_ and project_:
        raise click.UsageError("pass at most one of --global / --project")
    scope = _resolve_scope(global_, project_)
    project_root = str(Path.cwd()) if scope == "project" else None
    try:
        manifest = load(ref)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc
    try:
        bundle_install.run(
            manifest, scope=scope, dry_run=False, project_root=project_root
        )
    except bundle_install.BundleInstallError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"installed bundle {manifest.name!r} ({len(manifest.members)} members, {scope})")


def _resolve_scope(global_: bool, project_: bool) -> str:
    """No flag → toolkit default via the shared `default_scope` helper (F3):
    project inside a project (a per-kind lock present in cwd), else global."""
    if global_:
        return "global"
    if project_:
        return "project"
    return default_scope(Path.cwd())
