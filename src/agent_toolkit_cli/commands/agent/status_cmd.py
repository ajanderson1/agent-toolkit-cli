"""`agent status [slugs] [-g/-p]` — per-agent source + projection state."""
from __future__ import annotations

import click

from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import lock_file_path
from agent_toolkit_cli.commands.agent._common import scope_and_roots


def _projected_harnesses(slug: str, scope: str, home: object, project: object) -> list[str]:
    """Return list of harness names that have a live projection on disk."""
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    from agent_toolkit_cli.skill_agents import AGENTS
    from pathlib import Path

    found = []
    for name, cfg in AGENTS.items():
        if cfg.subagent_mechanism == "none":
            continue
        try:
            adapter = get_adapter(name)
            dest = adapter.destination(
                slug, scope=scope,
                home=home if isinstance(home, Path) else None,
                project=project if isinstance(project, Path) else None,
            )
            if dest.exists() or dest.is_symlink():
                found.append(name)
        except (UnsupportedMechanismError, ValueError, Exception):
            pass
    return sorted(found)


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
    """Show source and projection state for each agent."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    try:
        lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    except FileNotFoundError:
        # No lock file at all — name the scope so the wrong-scope case is legible
        # (the reporter's `list -g` vs bare `status` confusion in #304).
        click.echo(f"no agents in the {scope} library")
        return

    # An empty-but-present lock must not render as a blank screen: name the scope,
    # matching `agent list`'s non-blank empty handling (#304 bug 1).
    if not lock.skills:
        click.echo(f"no agents in the {scope} library")
        return

    if slugs:
        # Report each requested slug, flagging the ones absent from the library —
        # never let a no-match filter masquerade as an empty library.
        for slug in slugs:
            entry = lock.skills.get(slug)
            if entry is None:
                click.echo(f"{slug}\tnot found")
                continue
            harnesses = _projected_harnesses(slug, scope, home, project_root)
            projected = ", ".join(harnesses) if harnesses else "-"
            click.echo(f"{slug}\t{entry.source}\t{projected}")
        return

    for slug, entry in sorted(lock.skills.items()):
        harnesses = _projected_harnesses(slug, scope, home, project_root)
        projected = ", ".join(harnesses) if harnesses else "-"
        click.echo(f"{slug}\t{entry.source}\t{projected}")
