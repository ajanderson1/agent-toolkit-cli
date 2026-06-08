"""`agent list [-g/-p] [--json]` — list agents in the lock + projection state.

Read-only inventory: reads the agents-lock.json and checks each adapter's
destination to determine projection state. Defaults to global scope outside
a project (read_only=True).
"""
from __future__ import annotations

import json

import click

from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.table import render_table
from agent_toolkit_cli.agent_paths import lock_file_path
from agent_toolkit_cli.commands.agent._common import scope_and_roots


def _count_projections(slug: str, scope: str, home: object, project: object) -> int:
    """Count how many adapter destinations exist on disk for this slug."""
    from agent_toolkit_cli.agent_adapters import UnsupportedMechanismError, get_adapter
    from agent_toolkit_cli.skill_agents import AGENTS
    from pathlib import Path

    count = 0
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
                count += 1
        except (UnsupportedMechanismError, ValueError, Exception):
            pass
    return count


@click.command("list", epilog="""\
Examples:

\b
  agent-toolkit-cli agent list              # default scope
  agent-toolkit-cli agent list -g           # global library
  agent-toolkit-cli agent list -p           # project scope
  agent-toolkit-cli agent list --json       # machine-readable output
""")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON.")
@click.pass_context
def list_cmd(
    ctx: click.Context,
    global_: bool,
    project_flag: bool,
    as_json: bool,
) -> None:
    """List agents in the lock file with projection state."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    try:
        lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    except FileNotFoundError:
        if as_json:
            click.echo("[]")
        else:
            click.echo("no agents found")
        return

    if as_json:
        records = []
        for slug, entry in sorted(lock.skills.items()):
            projected = _count_projections(slug, scope, home, project_root) > 0
            records.append({
                "slug": slug,
                "source": entry.source,
                "sourceType": entry.source_type,
                "ref": entry.ref,
                "projected": projected,
                "scope": scope,
            })
        click.echo(json.dumps(records, indent=2))
        return

    if not lock.skills:
        click.echo("no agents found")
        return

    rows = []
    for slug, entry in sorted(lock.skills.items()):
        n = _count_projections(slug, scope, home, project_root)
        marker = "✔" if n > 0 else "☐"
        ref_display = f"@{entry.ref}" if entry.ref else ""
        rows.append([marker, slug, f"{entry.source}{ref_display}", f"[{n} harnesses]"])
    click.echo(render_table(rows))
