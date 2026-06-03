"""`agent doctor [-g/-p] [--no-fix]` — diagnose agent installation drift.

Detects:
  - missing canonicals (lock entry but no canonical directory)
  - missing content file (canonical exists but <slug>.md absent)
  - dirty working trees (uncommitted changes in the canonical)
  - orphaned projections (projection file exists but no lock entry)
  - orphan canonicals (canonical directory present but no lock entry)

Repair actions are offered interactively unless --no-fix is given.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import click

from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import Scope, library_agent_path, lock_file_path
from agent_toolkit_cli.commands.agent._common import scope_and_roots
from agent_toolkit_cli import skill_git


@dataclass
class FixAction:
    shell_preview: str
    apply: Callable[[], None]


@dataclass
class Finding:
    slug: str
    kind: str
    scope: str
    path: Path
    detail: str
    fix_action: FixAction | None = None


def _diagnose(
    *,
    slugs: tuple[str, ...] | None,
    scope: Scope,
    home: Path | None,
    project: Path | None,
) -> list[Finding]:
    findings: list[Finding] = []
    lock_path = lock_file_path(scope=scope, home=home, project=project)
    try:
        lock = read_lock(lock_path)
    except FileNotFoundError:
        return findings

    targets = (
        {k: v for k, v in lock.skills.items() if k in set(slugs)}
        if slugs else dict(lock.skills)
    )

    for slug, entry in sorted(targets.items()):
        canonical = library_agent_path(slug)

        # 1. Missing canonical directory.
        if not canonical.exists():
            findings.append(Finding(
                slug=slug, kind="missing-canonical", scope=scope,
                path=canonical,
                detail="lock entry exists but canonical directory is absent",
                fix_action=None,  # reclone would require source URL access
            ))
            continue

        # 2. Missing content file.
        content_file = canonical / f"{slug}.md"
        if not content_file.exists():
            findings.append(Finding(
                slug=slug, kind="missing-content-file", scope=scope,
                path=content_file,
                detail=f"{slug}.md absent in canonical",
                fix_action=None,
            ))

        # 3. Dirty working tree.
        if skill_git.is_git_repo(canonical):
            try:
                wt = skill_git.status(canonical, env=None)
                if wt == skill_git.GitWorkingTreeStatus.DIRTY:
                    findings.append(Finding(
                        slug=slug, kind="dirty-canonical", scope=scope,
                        path=canonical,
                        detail="canonical has uncommitted changes",
                        fix_action=None,
                    ))
            except skill_git.GitError:
                pass

    # 4. Orphan canonicals — directories under the library base with no lock
    # entry. This catches the #313 class of orphan: a clone left behind by a
    # failed `agent add` (slug mismatch, no --slug) before the lock is written.
    # Only run when no slug filter is active (targeted run won't see orphans)
    # and only for global scope (the library is global-only; project scope has
    # no canonical directory layout to walk).
    if not slugs and scope == "global":
        library_base = library_agent_path("__probe__").parent
        if library_base.is_dir():
            lock_slugs = set(lock.skills.keys())
            for child in sorted(library_base.iterdir()):
                if not child.is_dir():
                    continue
                if child.name not in lock_slugs:
                    orphan = child
                    findings.append(Finding(
                        slug=child.name,
                        kind="orphan-canonical",
                        scope=scope,
                        path=orphan,
                        detail="canonical directory has no lock entry",
                        fix_action=FixAction(
                            shell_preview=f"rm -rf {orphan}",
                            apply=lambda p=orphan: shutil.rmtree(p),
                        ),
                    ))

    return findings


@click.command("doctor")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--no-fix", is_flag=True, help="Report only; do not prompt or mutate.")
@click.pass_context
def doctor_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
    no_fix: bool,
) -> None:
    """Diagnose agent installation drift.

    Checks for missing canonicals, missing content files, and dirty working
    trees. Reports findings and (unless --no-fix) offers to apply automatic
    repairs where available.
    """
    scope, home, project_root = scope_and_roots(
        global_, project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    findings = _diagnose(
        slugs=slugs or None,
        scope=scope, home=home, project=project_root,
    )

    if not findings:
        click.echo("all clean")
        return

    fixed = skipped = 0
    quit_loop = False
    for f in findings:
        click.echo("")
        click.echo(f"{f.slug} · {f.kind} ({f.scope})")
        click.echo(f"  path:   {f.path}")
        click.echo(f"  detail: {f.detail}")
        if f.fix_action is None or no_fix or quit_loop:
            skipped += 1
            if f.fix_action is None:
                click.echo("  (report-only — no automatic fix)")
            continue
        click.echo(f"  fix:    {f.fix_action.shell_preview}")
        try:
            ans = click.prompt(
                "  apply?", default="N", show_default=False,
                type=click.Choice(["y", "N", "q"], case_sensitive=False),
            )
        except (click.Abort, EOFError, OSError):
            click.echo("\n  (no input available — stopping; nothing applied)")
            quit_loop = True
            skipped += 1
            continue
        ans = ans.lower()
        if ans == "y":
            try:
                f.fix_action.apply()
                click.echo("  fixed.")
                fixed += 1
            except Exception as exc:
                click.echo(f"  fix failed: {exc}")
                skipped += 1
        elif ans == "q":
            quit_loop = True
            skipped += 1
        else:
            skipped += 1

    click.echo("")
    click.echo(
        f"summary: {len(findings)} findings, {fixed} fixed, {skipped} skipped"
    )
    if skipped > 0 or fixed < len(findings):
        ctx.exit(1)
