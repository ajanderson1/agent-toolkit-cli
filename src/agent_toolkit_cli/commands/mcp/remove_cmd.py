"""`mcp remove <slug> [-g/-p]` — uninstall from EVERY harness in the lock.

The destructive counterpart to `uninstall` (which detaches a named subset).
For a library-sourced kind there is no owned canonical to delete — the library
entry is kept — so remove == full-fan-out uninstall across every harness the
lock records at this scope.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.commands.mcp._common import scope_and_roots
from agent_toolkit_cli.mcp_adapters import UnsupportedMcpHarnessError
from agent_toolkit_cli.mcp_library import library_root
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock


@click.command("remove", epilog="""\
Examples:

\b
  agent-toolkit-cli mcp remove context7 -p
  agent-toolkit-cli mcp remove context7 -g
""")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def remove_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
) -> None:
    """Remove a MCP's projections from every harness recorded in the lock."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    effective_home = home if home is not None else Path.home()
    library = library_root(Path.home())

    # Snapshot the harnesses BEFORE remove() empties the lock, so the success
    # line names them. (remove() prints its own "nothing to remove" to stderr.)
    lock_path = lock_path_for_scope(scope, home=effective_home, project=project)
    targets = [e.harness for e in read_lock(lock_path).get(slug, [])]

    try:
        mcp_install.remove(
            slug=slug, scope=scope,
            library_root=library, home=effective_home, project=project,
        )
    except UnsupportedMcpHarnessError as exc:
        raise click.ClickException(str(exc)) from exc
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    if targets:
        click.echo(f"removed {slug} → {', '.join(targets)} ({scope} scope)")
    else:
        click.echo(f"{slug}: nothing to remove ({scope} scope)")
