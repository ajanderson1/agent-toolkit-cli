"""skill status subcommand."""
from __future__ import annotations

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    lock_file_path,
    parent_clone_path,
)

from ._common import scope_and_roots


@click.command("status", epilog="""\
Examples:

\b
  agent-toolkit-cli skill status              # all skills
  agent-toolkit-cli skill status journal      # one skill
""")
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
    """Show per-skill working-tree status (clean/dirty/missing)."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    targets = slugs or tuple(sorted(lock.skills))
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}\t(not in lock)")
            continue
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )
        if not canonical.exists():
            click.echo(f"{slug}\tmissing")
            continue
        if entry.parent_url is not None:
            # Monorepo skill — status lives in the parent clone, not the
            # symlinked subpath (which has no `.git/` of its own).
            owner, repo = entry.source.split("/", 1)
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
            )
            if not skill_git.is_git_repo(parent_dir):
                click.echo(f"{slug}\tcopy")
                continue
            wt = skill_git.status(parent_dir, env=None)
        elif not skill_git.is_git_repo(canonical):
            click.echo(f"{slug}\tcopy")
            continue
        else:
            wt = skill_git.status(canonical, env=None)
        state = (
            "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
        )
        click.echo(f"{slug}\t{state}")
