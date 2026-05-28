"""skill list subcommand."""
from __future__ import annotations

import json

import click

from agent_toolkit_cli.skill_agents import AGENTS
from agent_toolkit_cli.skill_install import _current_linked_agents
from agent_toolkit_cli.skill_lock import LockFile, read_lock
from agent_toolkit_cli.skill_paths import lock_file_path

from ._common import scope_and_roots


@click.command("list", epilog="""\
Default scope: project if <cwd>/skills-lock.json exists, otherwise global.

Examples:

\b
  agent-toolkit-cli skill list        # auto-detect (project or global)
  agent-toolkit-cli skill list -g     # global library
  agent-toolkit-cli skill list -p     # project-scope skills
""")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "-a", "--agent", "agent", default=None,
    help="Filter to skills currently symlinked into this agent.",
)
@click.option(
    "--json", "as_json", is_flag=True,
    help="Emit a JSON array instead of the human-readable table.",
)
@click.pass_context
def list_cmd(
    ctx: click.Context,
    global_: bool,
    project_flag: bool,
    agent: str | None,
    as_json: bool,
) -> None:
    """List installed skills from the lock file."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )

    if agent is not None and agent != "universal" and agent not in AGENTS:
        raise click.UsageError(f"unknown agent: {agent}")
    if agent == "general-skill":
        raise click.UsageError(
            "general-skill is a synthetic catalog entry, not a usable agent token"
        )

    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))

    slugs = sorted(lock.skills)
    if agent is not None:
        slugs = [
            s for s in slugs
            if agent in _current_linked_agents(
                slug=s, scope=scope, home=home, project=project_root,
            )
        ]

    if as_json:
        _emit_json(lock, slugs, scope)
        return
    _emit_table(lock, slugs, agent, scope=scope, project_flag_explicit=project_flag)


def _emit_json(lock: LockFile, slugs: list[str], scope: str) -> None:
    """Print a JSON array of skill records to stdout."""
    out = [
        {
            "slug": slug,
            "source": lock.skills[slug].source,
            "ref": lock.skills[slug].ref,
            "upstream_sha": lock.skills[slug].upstream_sha,
            "local_sha": lock.skills[slug].local_sha,
            "scope": scope,
        }
        for slug in slugs
    ]
    click.echo(json.dumps(out))


def _emit_table(
    lock: LockFile,
    slugs: list[str],
    agent: str | None,
    *,
    scope: str = "global",
    project_flag_explicit: bool = False,
) -> None:
    """Print the human-readable tab-separated table to stdout."""
    if not lock.skills:
        if project_flag_explicit and scope == "project":
            click.echo(
                '(no project skills here. Run "skill list -g" for the global '
                'library, or "-p" from inside a project)'
            )
        else:
            click.echo("(no skills installed)")
        return
    if not slugs:
        click.echo(f"(no skills linked into {agent})")
        return
    for slug in slugs:
        e = lock.skills[slug]
        ref = e.ref or "main"
        short = (e.upstream_sha or "")[:7]
        click.echo(f"{slug}\t{e.source}\t{ref}\t{short}")
