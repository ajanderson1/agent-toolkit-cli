from __future__ import annotations

import datetime as _dt
import re
import subprocess
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.command_lock import read_lock, write_lock
from agent_toolkit_cli.command_paths import canonical_command_dir, lock_file_path
from agent_toolkit_cli.commands.command._common import scope_and_roots, validate_slug


@click.command("push")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--direct", is_flag=True, help="Push directly to the tracked ref. Default pushes a PR branch.")
@click.pass_context
def push_cmd(ctx, slugs: tuple[str, ...], global_: bool, project_flag: bool, direct: bool):
    """Publish command self-improvements upstream."""
    scope, home, project, _ = scope_and_roots(global_, project_flag, ctx.obj.get("project_root") if ctx.obj else None)
    path = lock_file_path(scope=scope, home=home, project=project)
    lock = read_lock(path)
    targets = slugs or tuple(sorted(lock.skills))
    rejected = False
    for raw in targets:
        slug = validate_slug(raw)
        entry = lock.skills.get(slug)
        if entry is None:
            click.echo(f"{slug}: not in the {scope} lock")
            rejected = True
            continue
        if entry.read_only:
            click.echo(f"{slug}: read-only monorepo entry — open a PR against {entry.parent_url or entry.source}")
            continue
        canonical = canonical_command_dir(slug, scope=scope, home=home, project=project)
        if not skill_git.is_git_repo(canonical):
            click.echo(f"{slug}: no .git/ in canonical — cannot push")
            continue
        ref = skill_git.resolve_ref(entry.ref, canonical)
        status = skill_git.status(canonical, env=None)
        if status == skill_git.GitWorkingTreeStatus.CLEAN:
            try:
                div = skill_git.divergence(canonical, ref=ref, env=None)
            except skill_git.GitError:
                div = skill_git.Divergence.UP_TO_DATE
            if div is skill_git.Divergence.UP_TO_DATE:
                click.echo(f"{slug}: clean — nothing to push")
                continue
            if div in (skill_git.Divergence.BEHIND, skill_git.Divergence.DIVERGED):
                click.echo(f"{slug}: clean but {div.value} from origin — not pushing")
                continue
            if direct:
                skill_git.push(canonical, ref=ref, env=None)
                entry.local_sha = skill_git.head_sha(canonical, env=None)
                write_lock(path, lock)
                click.echo(f"{slug}: pushed")
            else:
                _push_via_pr(canonical, slug, ref)
            continue
        if direct:
            skill_git.commit_all(canonical, message=f"command({slug}): self-improvement {_utc_iso()}", env=None)
            skill_git.push(canonical, ref=ref, env=None)
            entry.local_sha = skill_git.head_sha(canonical, env=None)
            write_lock(path, lock)
            click.echo(f"{slug}: pushed")
        else:
            _push_via_pr(canonical, slug, ref)
    if rejected:
        ctx.exit(1)


def _push_via_pr(canonical: Path, slug: str, base_ref: str) -> None:
    branch = f"command/self-improvement-{_utc_basic_iso()}-{_slug_for_ref(slug)}"
    original = base_ref
    skill_git.checkout_new_branch(canonical, name=branch, env=None)
    try:
        try:
            skill_git.commit_all(canonical, message=f"command({slug}): self-improvement {_utc_iso()}", env=None)
        except skill_git.GitError:
            pass
        skill_git.push(canonical, ref=branch, env=None)
        click.echo(f"{slug}: pushed branch {branch}")
        pr = _open_pr(canonical, branch, base=base_ref, slug=slug)
        if pr:
            click.echo(f"  PR: {pr}")
        else:
            click.echo(f"  open a PR from branch {branch} into {base_ref}")
    finally:
        try:
            skill_git.checkout(canonical, ref=original, env=None)
        except skill_git.GitError:
            pass


_REF_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _slug_for_ref(slug: str) -> str:
    return _REF_SAFE_RE.sub("-", slug.lower()).strip("-") or "command"


def _utc_basic_iso() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def _open_pr(canonical: Path, branch: str, *, base: str, slug: str) -> str | None:
    import shutil
    if shutil.which("gh") is None:
        return None
    try:
        if subprocess.run(["gh", "auth", "status"], capture_output=True, text=True).returncode != 0:
            return None
        proc = subprocess.run(["gh", "pr", "create", "--base", base, "--head", branch, "--title", f"command({slug}): self-improvement", "--body", f"Automated command self-improvement for `{slug}`."], cwd=canonical, capture_output=True, text=True)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    m = re.search(r"https?://\S+", proc.stdout)
    return m.group(0) if m else None
