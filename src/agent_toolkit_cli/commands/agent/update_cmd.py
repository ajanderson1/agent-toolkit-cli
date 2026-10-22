"""`agent update [slugs] [-g/-p]` — fetch + merge upstream for store-owned agents.

Mirrors pi-extension update_cmd: reads from the lock, iterates over targets,
calls skill_git.fetch + skill_git.merge, and updates lock SHAs on success.
"""
from __future__ import annotations

import click
from pathlib import Path

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.agent_lock import read_lock, write_lock, clone_url_from_entry
from agent_toolkit_cli.agent_paths import canonical_agent_dir, agent_content_path, lock_file_path
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
        if entry.parent_url is not None:
            try:
                agent_content_path(canonical, slug, entry)
            except InstallError as exc:
                click.echo(str(exc))
                had_error = True
                continue
            canonical = canonical.resolve()
            for _ in Path(entry.agent_path or f"{slug}.md").parent.parts:
                canonical = canonical.parent
        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: no .git/ in canonical — cannot update; "
                f"remove and re-add to switch to git-managed"
            )
            had_error = True
            continue

        from agent_toolkit_cli.project_backing import verify_gitfile_worktree
        try:
            verify_gitfile_worktree(canonical)
        except InstallError as exc:
            click.echo(str(exc))
            had_error = True
            continue
        if not skill_git.remote_matches(canonical, clone_url_from_entry(entry), None):
            click.echo(f"{slug}: foreign origin; refusing update")
            had_error = True
            continue
        if skill_git.status(canonical, env=None) != skill_git.GitWorkingTreeStatus.CLEAN:
            click.echo(f"{slug}: dirty backing; refusing update")
            had_error = True
            continue
        if entry.ref_looks_pinned:
            click.echo(f"{slug}: SHA-pinned; unchanged")
            continue
        skill_git.fetch(canonical, env=None)
        ref = skill_git.resolve_ref(entry.ref, canonical)
        try:
            skill_git.pull_ff_only(canonical, ref=ref, env=None)
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
        # Keep the requested ref identity (including None/default) separate
        # from the branch observed for this update. Re-registration and cache
        # selection must not silently become a different explicit request.
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")

    if had_error:
        ctx.exit(1)
