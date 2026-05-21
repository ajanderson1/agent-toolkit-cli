"""skill push subcommand."""
from __future__ import annotations

import datetime as _dt

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock, write_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, lock_file_path

from ._common import scope_and_roots


@click.command("push", epilog="""\
Examples:

\b
  agent-toolkit-cli skill push                # push all dirty skills
  agent-toolkit-cli skill push journal        # push one skill
""")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def push_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
) -> None:
    """Commit and push self-improvements upstream. No-op when clean."""
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    targets = slugs or tuple(sorted(lock.skills))
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            continue
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )
        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: copy-mode (no .git/) — cannot push; remove and "
                f"re-add to switch to git-managed",
            )
            continue
        if skill_git.status(canonical, env=None) == skill_git.GitWorkingTreeStatus.CLEAN:
            click.echo(f"{slug}: clean — nothing to push")
            continue
        msg = f"self-improvement: {_dt.datetime.now(_dt.UTC).isoformat()}"
        skill_git.commit_all(canonical, message=msg, env=None)
        skill_git.push(canonical, ref=entry.ref or "main", env=None)
        entry.local_sha = skill_git.head_sha(canonical, env=None)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: pushed")
