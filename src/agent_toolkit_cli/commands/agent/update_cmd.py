"""`agent update [slugs] [-g/-p]` — fetch + merge upstream for store-owned agents.

Mirrors pi-extension update_cmd: reads from the lock, iterates over targets,
calls skill_git.fetch + skill_git.merge, and updates lock SHAs on success.
"""
from __future__ import annotations

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.agent_lock import read_lock, write_lock
from agent_toolkit_cli.agent_paths import library_agent_path, lock_file_path
from agent_toolkit_cli.commands.agent._common import scope_and_roots


@click.command("update", epilog="""\
Examples:

\b
  agent-toolkit-cli agent update              # update all agents
  agent-toolkit-cli agent update my-agent     # update one agent
""")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def update_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
) -> None:
    """Fetch + merge upstream for each store-owned agent."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    try:
        lock = read_lock(lock_path)
    except FileNotFoundError:
        click.echo("no agents lock found")
        return

    targets = slugs or tuple(sorted(lock.skills))
    had_error = False

    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_error = True
            continue

        canonical = library_agent_path(slug)
        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: no .git/ in canonical — cannot update; "
                f"remove and re-add to switch to git-managed"
            )
            had_error = True
            continue

        entry = lock.skills[slug]
        ref = entry.ref or "main"
        skill_git.fetch(canonical, env=None)
        try:
            skill_git.merge(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(f"{slug}: conflict during merge (resolve in working copy)")
            click.echo(exc.stderr)
            had_error = True
            continue

        entry.local_sha = skill_git.head_sha(canonical, env=None)
        try:
            entry.upstream_sha = skill_git.remote_head_sha(
                canonical, ref=ref, env=None,
            )
        except skill_git.GitError:
            pass
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")

    if had_error:
        ctx.exit(1)
