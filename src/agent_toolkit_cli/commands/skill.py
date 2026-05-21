"""`agent-toolkit-cli skill ...` subcommand group.

Add/update/push/remove/list/status verbs for the skill lock-file model.
Other asset kinds remain on the legacy walker path.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_install import InstallError, install
from agent_toolkit_cli.skill_lock import (
    LockEntry,
    add_entry,
    read_lock,
    write_lock,
)
from agent_toolkit_cli.skill_paths import (
    SUPPORTED_HARNESSES,
    canonical_skill_dir,
    lock_file_path,
)
from agent_toolkit_cli.skill_source import SourceParseError, parse_source


def _scope_and_roots(global_: bool, project: bool, ctx_project: Path | None):
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None
    project_root = ctx_project or Path.cwd()
    return "project", None, project_root


def _harness_tuple(harness: tuple[str, ...] | None) -> tuple[str, ...]:
    if not harness:
        return SUPPORTED_HARNESSES
    for h in harness:
        if h not in SUPPORTED_HARNESSES:
            raise click.UsageError(f"unknown harness: {h}")
    return tuple(harness)


@click.group()
def skill() -> None:
    """Manage skills via per-skill upstream git repos + skills-lock.json."""


@skill.command("add")
@click.argument("source", required=True)
@click.option(
    "--slug", default=None,
    help="Override the local slug (defaults to repo name).",
)
@click.option("--ref", default=None, help="Branch or tag to install.")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "--harness", multiple=True,
    help=f"Restrict to one or more of: {', '.join(SUPPORTED_HARNESSES)}.",
)
@click.pass_context
def add(
    ctx: click.Context,
    source: str,
    slug: str | None,
    ref: str | None,
    global_: bool,
    project_flag: bool,
    harness: tuple[str, ...],
) -> None:
    """Add a skill from SOURCE (owner/repo, URL, or local path)."""
    try:
        parsed = parse_source(source)
    except SourceParseError as exc:
        raise click.UsageError(str(exc)) from exc

    if slug is None:
        if parsed.owner_repo:
            slug = parsed.owner_repo.split("/", 1)[1]
        else:
            slug = Path(parsed.url).name
    if ref is not None:
        parsed = dataclasses.replace(parsed, ref=ref)

    scope, home, project_root = _scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    harnesses = _harness_tuple(harness)

    try:
        canonical = install(
            parsed=parsed, slug=slug, scope=scope,
            home=home, project=project_root, harnesses=harnesses, env=None,
        )
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc

    upstream_sha = skill_git.remote_head_sha(
        canonical, ref=parsed.ref or "main", env=None,
    )
    local_sha = skill_git.head_sha(canonical, env=None)

    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    entry = LockEntry(
        source=parsed.owner_repo or parsed.url,
        source_type=parsed.type,
        ref=parsed.ref,
        skill_path="SKILL.md",
        upstream_sha=upstream_sha,
        local_sha=local_sha,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))
    click.echo(f"added {slug} <- {parsed.url}")


@skill.command("list")
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.pass_context
def list_(ctx: click.Context, global_: bool, project_flag: bool) -> None:
    """List installed skills from the lock file."""
    scope, home, project_root = _scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock = read_lock(lock_file_path(scope=scope, home=home, project=project_root))
    if not lock.skills:
        click.echo("(no skills installed)")
        return
    for slug in sorted(lock.skills):
        e = lock.skills[slug]
        ref = e.ref or "main"
        short = (e.upstream_sha or "")[:7]
        click.echo(f"{slug}\t{e.source}\t{ref}\t{short}")


@skill.command("status")
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
    scope, home, project_root = _scope_and_roots(
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
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )
        if not canonical.exists():
            click.echo(f"{slug}\tmissing")
            continue
        wt = skill_git.status(canonical, env=None)
        state = (
            "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
        )
        click.echo(f"{slug}\t{state}")


@skill.command("update")
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
    """Fetch + merge upstream for each skill. Surfaces real git conflicts."""
    scope, home, project_root = _scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    targets = slugs or tuple(sorted(lock.skills))
    had_conflict = False
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_conflict = True
            continue
        entry = lock.skills[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )
        ref = entry.ref or "main"
        skill_git.fetch(canonical, env=None)
        try:
            skill_git.merge(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            click.echo(
                f"{slug}: conflict during merge (resolve in working copy)"
            )
            click.echo(exc.stderr)
            had_conflict = True
            continue
        entry.local_sha = skill_git.head_sha(canonical, env=None)
        entry.upstream_sha = skill_git.remote_head_sha(
            canonical, ref=ref, env=None,
        )
        write_lock(lock_path, lock)
        click.echo(f"{slug}: updated")
    if had_conflict:
        ctx.exit(1)


@skill.command("push")
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
    scope, home, project_root = _scope_and_roots(
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
        if skill_git.status(canonical, env=None) == skill_git.GitWorkingTreeStatus.CLEAN:
            click.echo(f"{slug}: clean — nothing to push")
            continue
        msg = f"self-improvement: {_dt.datetime.now(_dt.UTC).isoformat()}"
        skill_git.commit_all(canonical, message=msg, env=None)
        skill_git.push(canonical, ref=entry.ref or "main", env=None)
        entry.local_sha = skill_git.head_sha(canonical, env=None)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: pushed")
