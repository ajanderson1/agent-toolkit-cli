"""`mcp uninstall <slug> [--harness ...] [-g/-p]` — toggle projections OFF.

Removes the named MCP entry from each harness's config (non-destructive: the
library entry and any other-scope lock are untouched — use `mcp remove` to drop
from every harness). Default harnesses = those recorded in the resolved-scope
lock for this slug.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.commands.mcp._common import (
    _CHOICE_HARNESSES,
    normalize_harness_tokens,
    scope_and_roots,
)
from agent_toolkit_cli.mcp_adapters import UnsupportedMcpHarnessError
from agent_toolkit_cli.mcp_install import RunningClaudeError
from agent_toolkit_cli.mcp_library import library_root
from agent_toolkit_cli.mcp_lock import lock_path_for_scope, read_lock


@click.command("uninstall", epilog="""\
Examples:

\b
  agent-toolkit-cli mcp uninstall context7 -p
  agent-toolkit-cli mcp uninstall context7 -g --harness claude-code
""")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "--harness", "harnesses", multiple=True,
    type=click.Choice(_CHOICE_HARNESSES),
    help="Harness to remove from (repeatable). Default: every harness in the lock.",
)
@click.option(
    "--force", is_flag=True,
    help="Bypass the running-claude guard for ~/.claude.json writes.",
)
@click.pass_context
def uninstall_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
    harnesses: tuple[str, ...],
    force: bool,
) -> None:
    """Remove a MCP's projections from the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    effective_home = home if home is not None else Path.home()
    library = library_root(Path.home())

    if harnesses:
        targets = list(normalize_harness_tokens(tuple(harnesses), scope=scope))
    else:
        lock_path = lock_path_for_scope(scope, home=effective_home, project=project)
        lock = read_lock(lock_path)
        targets = [e.harness for e in lock.get(slug, [])]
        if not targets:
            raise click.ClickException(f"{slug} is not installed at {scope} scope")

    try:
        mcp_install.uninstall(
            slug=slug, harnesses=targets, scope=scope,
            library_root=library, home=effective_home, project=project,
            force=force,
        )
    except RunningClaudeError as exc:
        raise click.ClickException(str(exc)) from exc
    except UnsupportedMcpHarnessError as exc:
        raise click.ClickException(str(exc)) from exc
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"uninstalled {slug} → {', '.join(targets)} ({scope} scope)")
