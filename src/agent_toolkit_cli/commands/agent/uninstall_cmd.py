"""`agent uninstall <slug> [-g/-p] [--harnesses <names>]` — toggle projections OFF.

Keeps the canonical library entry (global store copy, lock entry).
Use `agent remove` to fully drop from the library.

result.removed is NOT populated by apply() (known gap in agent_install.apply):
we call agent_install.uninstall() directly which does correctly remove all
projected files via each adapter's uninstall() method.
"""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import agent_install
from agent_toolkit_cli.commands.agent._common import scope_and_roots
from agent_toolkit_cli.skill_agents import AGENTS


def _resolve_harnesses_for_uninstall(
    harnesses_str: str | None, slug: str, scope: str,
    home: object, project: object,
) -> tuple[str, ...]:
    """If --harnesses given, use that. Otherwise, derive from the lock entry."""
    if harnesses_str is not None:
        parts = [p.strip() for p in harnesses_str.split(",") if p.strip()]
        unknown = [p for p in parts if p not in AGENTS]
        if unknown:
            raise click.UsageError(f"unknown harness(es): {', '.join(unknown)}")
        return tuple(parts)
    # Default: all enabled harnesses (same as install default).
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    result = []
    for name, cfg in AGENTS.items():
        if cfg.subagent_mechanism == "none":
            continue
        try:
            get_adapter(name)
            result.append(name)
        except (UnsupportedMechanismError, Exception):
            pass
    return tuple(sorted(result))


@click.command("uninstall", epilog="""\
Examples:

\b
  agent-toolkit-cli agent uninstall my-agent -g
  agent-toolkit-cli agent uninstall my-agent -p
  agent-toolkit-cli agent uninstall my-agent -g --harnesses claude-code
""")
@click.argument("slug")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "--harnesses", default=None,
    help="Comma-separated harness names to remove from. Default: all enabled.",
)
@click.pass_context
def uninstall_cmd(
    ctx: click.Context,
    slug: str,
    global_: bool,
    project_flag: bool,
    harnesses: str | None,
) -> None:
    """Remove an agent's projections from the chosen scope."""
    scope, home, project = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )

    try:
        target_harnesses = _resolve_harnesses_for_uninstall(
            harnesses, slug, scope, home, project,
        )
    except click.UsageError:
        raise

    # agent_install.uninstall() directly calls each adapter's uninstall()
    # and drops the lock entry. This is the correct path that avoids the
    # orphaned-projection bug (result.removed is empty from apply() — see
    # agent_install.apply() code: the removed list is never populated).
    #
    # Pass explicit home=Path.home() for global scope so adapters can resolve
    # {HOME} path templates (home=None causes ValueError in symlink._expand).
    effective_home = home if home is not None else (Path.home() if scope == "global" else None)
    agent_install.uninstall(
        slug=slug, scope=scope, home=effective_home, project=project,
        harnesses=target_harnesses,
    )
    click.echo(f"uninstalled {slug} [{scope}]")
