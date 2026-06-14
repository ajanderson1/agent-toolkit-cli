"""`agent push [slugs] [-g/-p] [--direct]` — push local commits upstream.

Mirrors pi-extension push_cmd including the clean-gap fix (#280): a clean
working tree that is AHEAD of origin still has committed-but-unpushed work
to publish. Default opens a PR; --direct pushes straight to the ref.
"""
from __future__ import annotations

import datetime as _dt
import re
import subprocess
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.agent_lock import read_lock, write_lock
from agent_toolkit_cli.agent_paths import library_agent_path, lock_file_path
from agent_toolkit_cli.commands.agent._common import scope_and_roots, scope_banner


@click.command("push", epilog="""\
Examples:

\b
  agent-toolkit-cli agent push                    # push all agents
  agent-toolkit-cli agent push my-agent           # push one agent
  agent-toolkit-cli agent push --direct my-agent  # push straight to ref
""")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option(
    "--direct", is_flag=True,
    help="Push directly to the tracked ref. Default opens a PR.",
)
@click.pass_context
def push_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
    direct: bool,
) -> None:
    """Publish self-improvements upstream. Opens a PR by default."""
    ctx_project = ctx.obj.get("project_root") if ctx.obj else None
    scope, home, project_root, implicit = scope_and_roots(
        global_,
        project_flag,
        ctx_project,
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
    rejected = False

    for slug in targets:
        if slug not in lock.skills:
            click.echo(_missing_slug_message(slug, scope, ctx_project))
            rejected = True
            continue

        canonical = library_agent_path(slug)
        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: no .git/ in canonical — cannot push; "
                f"remove and re-add to switch to git-managed"
            )
            continue

        entry = lock.skills[slug]
        ref = skill_git.resolve_ref(entry.ref, canonical)
        wt = skill_git.status(canonical, env=None)

        if wt == skill_git.GitWorkingTreeStatus.CLEAN:
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
            # AHEAD: committed-but-unpushed work.
            if direct:
                skill_git.push(canonical, ref=ref, env=None)
                entry.local_sha = skill_git.head_sha(canonical, env=None)
                write_lock(lock_path, lock)
                click.echo(f"{slug}: pushed (committed-but-unpushed → {ref})")
            else:
                _push_via_pr(canonical, entry, slug, ref)
            continue

        # Dirty tree: commit + push.
        if direct:
            msg = f"agent({slug}): self-improvement {_utc_iso()}"
            skill_git.commit_all(canonical, message=msg, env=None)
            skill_git.push(canonical, ref=ref, env=None)
            entry.local_sha = skill_git.head_sha(canonical, env=None)
            write_lock(lock_path, lock)
            click.echo(f"{slug}: pushed")
        else:
            _push_via_pr(canonical, entry, slug, ref)

    if rejected:
        ctx.exit(1)


def _missing_slug_message(
    slug: str, scope: str, ctx_project: Path | None,
) -> str:
    """Message for an explicitly named slug missing from the resolved scope's
    lock (#371). Probes the OTHER scope's lock so a slug that lives there gets
    a re-run hint instead of a bare "not in lock". `read_lock` returns an
    empty lock for a missing/corrupt file, so the probe never raises. The
    project root is re-derived here because `scope_and_roots` returns
    `project_root=None` at global scope even when the cwd is a project."""
    if scope == "project":
        other = read_lock(lock_file_path(scope="global", home=Path.home()))
        if slug in other.skills:
            return (
                f"{slug}: not in the project lock "
                f"(found in the global lock — re-run with -g)"
            )
        return f"{slug}: not in the project lock"
    other_root = ctx_project or Path.cwd()
    other = read_lock(lock_file_path(scope="project", project=other_root))
    if slug in other.skills:
        return (
            f"{slug}: not in the global lock "
            f"(found in the project lock — re-run with -p)"
        )
    return f"{slug}: not in the global lock"


def _push_via_pr(canonical: Path, entry: object, slug: str, base_ref: str) -> None:
    """Commit local changes on a branch and open a PR (mirrors pi-extension push)."""
    branch = f"agent/self-improvement-{_utc_basic_iso()}-{_slug_for_ref(slug)}"
    skill_git.checkout_new_branch(canonical, name=branch, env=None)
    msg = f"agent({slug}): self-improvement {_utc_iso()}"
    try:
        skill_git.commit_all(canonical, message=msg, env=None)
    except skill_git.GitError:
        pass  # nothing to commit (AHEAD case — already committed)
    try:
        skill_git.push(canonical, ref=branch, env=None)
        click.echo(f"{slug}: pushed branch {branch}")
        pr_url = _open_pr(canonical, branch, base=base_ref, slug=slug)
        if pr_url:
            click.echo(f"  PR: {pr_url}")
        else:
            web = _branch_web_url(canonical, branch)
            if web:
                click.echo(f"  open a PR: {web}")
            click.echo(f"  (rerun with --direct to push to {base_ref})")
    finally:
        skill_git.checkout(canonical, ref=base_ref, env=None)


_REF_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _slug_for_ref(slug: str) -> str:
    cleaned = _REF_SAFE_RE.sub("-", slug.lower()).strip("-")
    return cleaned or "agent"


def _utc_basic_iso() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def _open_pr(canonical: Path, branch: str, *, base: str, slug: str) -> str | None:
    import shutil
    if shutil.which("gh") is None:
        return None
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True,
        )
        if proc.returncode != 0:
            return None
    except OSError:
        return None
    title = f"agent({slug}): self-improvement"
    body = (
        f"Automated self-improvement push from agent-toolkit-cli.\n\n"
        f"Slug: `{slug}`\nBranch: `{branch}` → `{base}`\n"
    )
    try:
        proc = subprocess.run(
            ["gh", "pr", "create", "--base", base, "--head", branch,
             "--title", title, "--body", body],
            cwd=str(canonical), capture_output=True, text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    m = re.search(r"https?://\S+", proc.stdout)
    return m.group(0) if m else None


_GITHUB_SSH_RE = re.compile(r"^git@github\.com:(?P<path>[^/]+/[^/]+?)(?:\.git)?$")
_GITHUB_HTTPS_RE = re.compile(
    r"^https?://github\.com/(?P<path>[^/]+/[^/]+?)(?:\.git)?/?$"
)


def _branch_web_url(canonical: Path, branch: str) -> str | None:
    try:
        url = skill_git.remote_url(canonical, env=None)
    except skill_git.GitError:
        return None
    for pattern in (_GITHUB_SSH_RE, _GITHUB_HTTPS_RE):
        m = pattern.match(url)
        if m:
            return f"https://github.com/{m.group('path')}/tree/{branch}"
    return None
