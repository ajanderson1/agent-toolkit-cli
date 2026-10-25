"""skill status subcommand."""
from __future__ import annotations

from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    lock_file_path,
    project_parents_root,
    resolve_existing_parent_clone,
)

from ._common import scope_and_roots, scope_banner


def _divergence_suffix(parent_dir: Path, ref: str) -> str:
    """`, ahead N`/`, behind N`/`, diverged` marker for a monorepo parent, or
    "" when up-to-date or the comparison can't be made.

    Reads local refs only (no fetch), so an unpushed local commit reliably
    shows as ahead of the last-known origin. Never raises into the status loop.
    """
    try:
        div = skill_git.divergence(parent_dir, ref=ref, env=None)
    except Exception:
        return ""
    if div is skill_git.Divergence.AHEAD:
        return ", ahead (unpushed)"
    if div is skill_git.Divergence.BEHIND:
        return ", behind"
    if div is skill_git.Divergence.DIVERGED:
        return ", diverged"
    return ""


@click.command("status", epilog="""\
Default scope: project if <cwd>/skills-lock.json exists, otherwise global.

Examples:

\b
  agent-toolkit-cli skill status              # all skills (auto-detect scope)
  agent-toolkit-cli skill status journal      # one skill
  agent-toolkit-cli skill status -g           # force global library
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
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    scope_banner(scope, implicit=implicit, lock_path=lock_path, count=len(lock.skills))
    if not lock.skills and project_flag and scope == "project":
        click.echo(
            '(no project skills here. Run "skill status -g" for the global '
            'library, or "-p" from inside a project)'
        )
        return
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
            if scope == "project":
                # project scope always carries a project_root (scope_and_roots
                # only returns scope=="project" with a non-None project_root).
                assert project_root is not None
                parents_root = project_parents_root(project_root)
            else:
                parents_root = None
            parent_dir = resolve_existing_parent_clone(
                owner, repo, ref=entry.ref, parent_url=entry.parent_url,
                env=None,
                root=parents_root,
            )
            # Central project backing may live in the global checkout rather
            # than the project's legacy _parents directory. Prefer the actual
            # canonical only when its Git origin proves the recorded source.
            actual_parent = canonical.resolve()
            for _ in Path(entry.skill_path or ".").parts:
                actual_parent = actual_parent.parent
            if skill_git.is_git_repo(actual_parent) and skill_git.remote_matches(
                actual_parent, entry.parent_url, None,
            ):
                parent_dir = actual_parent
            if not skill_git.is_git_repo(parent_dir):
                click.echo(f"{slug}\tcopy")
                continue
            wt = skill_git.status_path(parent_dir, entry.skill_path or ".", env=None)
            if not entry.read_only:
                # Owned entries retain their writable/divergence annotation;
                # every child's working-tree badge is scoped to its own path.
                state = (
                    "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                    else "clean"
                )
                # A clean working tree is not the whole story: a committed but
                # unpushed change leaves the tree clean yet HEAD ahead of
                # origin. Surface it so "clean" doesn't read as "in sync with
                # remote" (#276). divergence() reads local refs only (no fetch),
                # so an unpushed commit shows as AHEAD against the last-known
                # origin regardless of fetch freshness.
                suffix = _divergence_suffix(
                    parent_dir, skill_git.resolve_ref(entry.ref, parent_dir),
                )
                click.echo(f"{slug}\t{state} (owned){suffix}")
                continue
        elif not skill_git.is_git_repo(canonical):
            click.echo(f"{slug}\tcopy")
            continue
        else:
            wt = skill_git.status(canonical, env=None)
        state = (
            "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
        )
        click.echo(f"{slug}\t{state}")
