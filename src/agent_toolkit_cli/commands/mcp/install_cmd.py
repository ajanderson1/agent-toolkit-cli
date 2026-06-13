"""`mcp install <slug> [--harness ...] [-g/-p] [--force]` — project to harnesses.

Injects the library MCP entry into each requested harness's native config via
the per-harness adapter, writing mcps-lock.json. Default harnesses = all four.
Write verb: defaults to project scope when a project lock is present.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import mcp_install
from agent_toolkit_cli.commands.mcp._common import _HARNESSES, scope_and_roots
from agent_toolkit_cli.mcp_adapters import UnsupportedMcpHarnessError
from agent_toolkit_cli.mcp_install import RunningClaudeError
from agent_toolkit_cli.mcp_library import library_root


@click.command("install", epilog="""\
Examples:

\b
  agent-toolkit-cli mcp install context7 -p
  agent-toolkit-cli mcp install context7 -g --harness claude-code
  agent-toolkit-cli mcp install context7 -g --harness claude-code --harness codex
""")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "--harness", "harnesses", multiple=True,
    type=click.Choice(_HARNESSES),
    help="Harness to install into (repeatable). Default: all four.",
)
@click.option(
    "--force", is_flag=True,
    help="Bypass the running-claude guard for ~/.claude.json writes.",
)
@click.pass_context
def install_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
    harnesses: tuple[str, ...],
    force: bool,
) -> None:
    """Project a library MCP into the chosen scope's harnesses."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    # Path.home() is read at RUNTIME (honors a test's monkeypatched HOME).
    effective_home = home if home is not None else Path.home()
    library = library_root(Path.home())
    targets = list(harnesses) or list(_HARNESSES)

    try:
        result = mcp_install.apply(
            slug=slug, harnesses=targets, scope=scope,
            library_root=library, home=effective_home, project=project,
            force=force,
        )
    except RunningClaudeError as exc:
        raise click.ClickException(str(exc)) from exc
    except UnsupportedMcpHarnessError as exc:
        raise click.ClickException(str(exc)) from exc
    except FileNotFoundError as exc:
        # Absent library slug (load_mcp_asset raises with a remediation hint).
        raise click.ClickException(str(exc)) from exc

    if result.installed:
        click.echo(
            f"✓ installed {slug} → {', '.join(result.installed)} ({scope} scope)"
        )
    else:
        click.echo(f"{slug}: nothing installed ({scope} scope)")
    if result.skipped:
        click.echo(f"  skipped (harness not installed): {', '.join(result.skipped)}")
    if result.collisions:
        click.echo(
            f"  overwrote hand-rolled entries in: {', '.join(result.collisions)}"
        )
