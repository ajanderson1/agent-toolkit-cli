"""`agent update [slugs] [-g/-p]` — fetch + merge upstream for store-owned agents.

Mirrors pi-extension update_cmd: reads from the lock, iterates over targets,
calls skill_git.fetch + skill_git.merge, and updates lock SHAs on success.
"""
from __future__ import annotations

import click
from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.agent_lock import read_lock, write_lock, clone_url_from_entry
from agent_toolkit_cli.agent_paths import (
    canonical_agent_dir, agent_git_root, registered_agent_paths, refresh_agent_repo, lock_file_path,
)
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.commands.agent._common import scope_and_roots, scope_banner


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
    scope, home, project_root, implicit = scope_and_roots(
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

    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))

    targets = slugs or tuple(sorted(lock.skills))
    had_error = False

    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_error = True
            continue

        entry = lock.skills[slug]
        canonical = canonical_agent_dir(slug, scope=scope, home=home, project=project_root)
        try:
            root = agent_git_root(canonical, slug, entry, project=project_root if scope == "project" else None)
            if entry.ref_looks_pinned:
                click.echo(f"{slug}: SHA-pinned; unchanged")
                continue
            paths = registered_agent_paths(root, library=lock if scope == "global" else None,
                                           scoped=lock if scope == "project" else None, project=project_root)
            relative = entry.agent_path or f"{slug}.md"
            paths[slug] = Path(relative).name if root == canonical.resolve() else relative
            target, _chosen = refresh_agent_repo(root, source_url=clone_url_from_entry(entry), ref=entry.ref, paths=paths)
        except (InstallError, skill_git.GitError) as exc:
            click.echo(f"{slug}: update refused: {exc}")
            had_error = True
            continue

        entry.local_sha = skill_git.head_sha(root, env=None)
        entry.upstream_sha = target
        # Keep the requested ref identity (including None/default) separate
        # from the branch observed for this update. Re-registration and cache
        # selection must not silently become a different explicit request.
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")

    if had_error:
        ctx.exit(1)
