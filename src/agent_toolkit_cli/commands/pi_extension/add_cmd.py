"""`pi-extension add <source>` — global-only (mirror `skill add`)."""
from __future__ import annotations

import click

from agent_toolkit_cli import pi_extension_add
from agent_toolkit_cli.skill_git import GitError


@click.command("add")
@click.argument("source")
@click.option("--slug", default=None, help="Override the derived slug.")
def add_cmd(source: str, slug: str | None) -> None:
    """Add a Pi extension to the global library (clone or npm record).

    Git sources must address a repository root, not a subdirectory. Existing
    unregistered checkouts are registered only if their origin matches SOURCE.
    Registration does not activate the extension; use install separately.
    """
    try:
        ext_slug = pi_extension_add.add(source=source, slug=slug, env=None)
    except (pi_extension_add.AddError, GitError) as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"added {ext_slug}")
