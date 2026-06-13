"""`mcp status [slugs] [-g/-p]` — print the resolved-scope lock contents.

Read-only: defaults to global outside a project. Shows each locked slug, the
harnesses it is projected into, and the recorded pin per harness.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli.commands.mcp._common import scope_and_roots
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock


@click.command("status")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def status_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
) -> None:
    """Show locked MCP projection state for each slug."""
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    effective_home = home if home is not None else Path.home()
    lock = read_lock(lock_path_for_scope(scope, home=effective_home, project=project_root))

    if not lock:
        click.echo(f"no MCP servers in the {scope} lock")
        return

    if slugs:
        for slug in slugs:
            entries = lock.get(slug)
            if not entries:
                click.echo(f"{slug}\tnot found")
                continue
            _echo_slug(slug, entries)
        return

    for slug in sorted(lock):
        _echo_slug(slug, lock[slug])


def _echo_slug(slug: str, entries: list) -> None:
    """One line per (slug, harness): `<slug>\t<harness>\t<pin|floating>`."""
    for entry in sorted(entries, key=lambda e: e.harness):
        pin = entry.pin if entry.pin else "floating"
        click.echo(f"{slug}\t{entry.harness}\t{pin}")
