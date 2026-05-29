"""skill push subcommand."""
from __future__ import annotations

import datetime as _dt
import functools
import re
import secrets
import shutil
import subprocess
from pathlib import Path

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import LockFile, read_lock, write_lock
from agent_toolkit_cli.skill_ownership import is_owned_owner
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir,
    lock_file_path,
    parent_clone_path,
    project_parents_root,
)

from ._common import scope_and_roots


@click.command("push", epilog="""\
Examples:

\b
  agent-toolkit-cli skill push                # push all dirty skills as PRs
  agent-toolkit-cli skill push journal        # push one skill as a PR
  agent-toolkit-cli skill push --direct mkdocs  # legacy: commit straight to tracked ref
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
    # Memoise gh-availability for the lifetime of this invocation so a
    # batch `skill push` doesn't spawn `gh auth status` per slug.
    _gh_available.cache_clear()
    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
        read_only=True,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)
    targets = slugs or tuple(sorted(lock.skills))
    rejected = False
    for slug in targets:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            continue
        entry = lock.skills[slug]
        if entry.read_only:
            click.echo(
                f"{slug}: read-only (monorepo skill from {entry.parent_url}); "
                f"`skill push` is rejected. Open a PR against the parent repo."
            )
            rejected = True
            continue
        if entry.parent_url is not None:
            # Owned monorepo (read_only already excluded above): push the
            # skill's subpath within the shared parent clone. Isolate per-slug
            # failures so one skill's git error doesn't abort a batch push and
            # strand the shared clone for its siblings.
            try:
                _push_monorepo(
                    entry, slug, lock=lock, lock_path=lock_path,
                    scope=scope, project_root=project_root, direct=direct,
                )
            except skill_git.GitError as exc:
                click.echo(f"{slug}: push failed in parent clone — {exc}")
                rejected = True
            continue
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
            # A clean working tree is not the whole story: a committed-but-
            # unpushed change leaves the tree clean yet HEAD ahead of origin.
            # Reporting "nothing to push" here silently strands that work
            # (#280). Classify divergence before declaring nothing to do.
            ref = entry.ref or "main"
            div = _clean_divergence(canonical, ref)
            if div is skill_git.Divergence.UP_TO_DATE:
                click.echo(f"{slug}: clean — nothing to push")
                continue
            if div in (skill_git.Divergence.BEHIND, skill_git.Divergence.DIVERGED):
                click.echo(f"{slug}: clean but {div.value} origin — not pushing")
                continue
            # AHEAD: committed-but-unpushed work to publish (already committed,
            # so no commit step — just push HEAD).
            if direct:
                _push_committed_direct(canonical, entry, slug, lock, lock_path, ref)
            else:
                _push_committed_via_pr(canonical, entry, slug, ref)
            continue
        if direct:
            _push_direct(canonical, entry, slug, lock, lock_path)
        else:
            _push_via_pr(canonical, entry, slug)
    if rejected:
        ctx.exit(1)


def _push_direct(
    canonical: Path,
    entry,
    slug: str,
    lock: LockFile,
    lock_path: Path,
) -> None:
    msg = f"self-improvement: {_utc_iso()}"
    skill_git.commit_all(canonical, message=msg, env=None)
    skill_git.push(canonical, ref=entry.ref or "main", env=None)
    entry.local_sha = skill_git.head_sha(canonical, env=None)
    write_lock(lock_path, lock)
    click.echo(f"{slug}: pushed")


def _push_via_pr(canonical: Path, entry, slug: str) -> None:
    base_ref = entry.ref or "main"
    branch = f"skill/self-improvement-{_utc_basic_iso()}-{_slug_for_ref(slug)}"
    # checkout -b then immediately commit_all — the working-tree changes
    # carry onto the new branch and become the first commit. The branch is
    # then pushed; we always check the canonical repo back to base_ref so a
    # subsequent `skill update` merges into the tracked ref, not the PR
    # branch we just created.
    skill_git.checkout_new_branch(canonical, name=branch, env=None)
    msg = f"self-improvement: {_utc_iso()}"
    skill_git.commit_all(canonical, message=msg, env=None)
    try:
        skill_git.push(canonical, ref=branch, env=None)
        click.echo(f"{slug}: pushed branch {branch}")
        pr_url = _open_pr(canonical, branch, base=base_ref, slug=slug)
        if pr_url:
            click.echo(f"  PR: {pr_url}")
        else:
            web = _branch_web_url(canonical, branch)
            if web:
                click.echo(f"  → open a PR: {web}")
            click.echo(f"  (rerun with --direct to push to {base_ref})")
    finally:
        skill_git.checkout(canonical, ref=base_ref, env=None)


def _clean_divergence(repo: Path, ref: str) -> skill_git.Divergence:
    """Classify a clean repo's HEAD vs origin/<ref> so `push` can tell a
    committed-but-unpushed clone (AHEAD) from a truly-nothing-to-push one
    (#280). Reads local refs only (no fetch), so an unpushed commit reliably
    shows AHEAD regardless of fetch freshness — same stance as
    `status._divergence_suffix`.

    A clone whose origin ref can't be resolved (detached / missing remote-
    tracking ref) raises GitError; treat that as UP_TO_DATE so an
    unclassifiable repo falls back to today's "nothing to push" rather than
    blindly pushing — mirrors the swallow-to-empty behaviour in `status`.
    """
    try:
        return skill_git.divergence(repo, ref=ref, env=None)
    except skill_git.GitError:
        return skill_git.Divergence.UP_TO_DATE


def _push_committed_direct(
    canonical: Path,
    entry,
    slug: str,
    lock: LockFile,
    lock_path: Path,
    ref: str,
) -> None:
    """Push already-committed work straight to the tracked ref. No commit step
    — the working tree is clean and HEAD is ahead of origin (#280)."""
    skill_git.push(canonical, ref=ref, env=None)
    entry.local_sha = skill_git.head_sha(canonical, env=None)
    write_lock(lock_path, lock)
    click.echo(f"{slug}: pushed (committed-but-unpushed → {ref})")


def _push_committed_via_pr(canonical: Path, entry, slug: str, base_ref: str) -> None:
    """Open a PR for already-committed work. Branches at the current HEAD
    (which carries the ahead commits) and pushes that branch — no commit step,
    unlike `_push_via_pr`. The canonical repo is restored to base afterward so
    a later `skill update` merges into the tracked ref (#280)."""
    branch = f"skill/self-improvement-{_utc_basic_iso()}-{_slug_for_ref(slug)}"
    skill_git.checkout_new_branch(canonical, name=branch, env=None)
    try:
        skill_git.push(canonical, ref=branch, env=None)
        click.echo(f"{slug}: pushed branch {branch}")
        pr_url = _open_pr(canonical, branch, base=base_ref, slug=slug)
        if pr_url:
            click.echo(f"  PR: {pr_url}")
        else:
            web = _branch_web_url(canonical, branch)
            if web:
                click.echo(f"  → open a PR: {web}")
            click.echo(f"  (rerun with --direct to push to {base_ref})")
    finally:
        skill_git.checkout(canonical, ref=base_ref, env=None)


def _monorepo_parent_dir(entry, scope: str, project_root) -> Path:
    owner, repo = entry.source.split("/", 1)
    return parent_clone_path(
        owner, repo, ref=entry.ref, env=None,
        root=project_parents_root(project_root) if scope == "project" else None,
    )


def _push_monorepo(
    entry, slug: str, *, lock: LockFile, lock_path: Path,
    scope: str, project_root, direct: bool,
) -> None:
    """Push an owned-monorepo skill's subpath within the shared parent clone.

    Subpath-scoped commit + one PR branch per push: stage/commit only the
    skill's `skill_path`, so a dirty sibling subpath sharing the parent clone
    is never swept into the commit. The clone is restored to the base ref
    afterward via a plain checkout that preserves any sibling's uncommitted
    edits, so a later `skill update` merges into the tracked ref.
    """
    parent_dir = _monorepo_parent_dir(entry, scope, project_root)
    if not skill_git.is_git_repo(parent_dir):
        click.echo(
            f"{slug}: parent clone missing or not a git repo at {parent_dir}"
        )
        return
    # Subpath isolation is the whole point of this path; a falsey skill_path
    # would scope to "." and sweep every sibling into the commit, so refuse it
    # rather than silently push the entire monorepo.
    if not entry.skill_path:
        click.echo(
            f"{slug}: lock entry has no skillPath — refusing to push the whole "
            f"monorepo. Remove and re-add the skill."
        )
        return
    subpath = entry.skill_path
    # Defense-in-depth: the writable decision was made at add-time and persisted
    # as the absence of readOnly. Re-derive ownership at push time so a foreign
    # or hand-edited lock entry can't quietly open a PR against a parent the
    # user doesn't own without at least surfacing it.
    owner = entry.source.split("/", 1)[0]
    if not is_owned_owner(owner):
        click.echo(
            f"  warning: {entry.source} is not a known owned owner; pushing "
            f"because the lock entry is writable (added with --owned?)."
        )
    base_ref = entry.ref or "main"
    if skill_git.status_path(parent_dir, subpath, env=None) == \
            skill_git.GitWorkingTreeStatus.CLEAN:
        # Clean subpath doesn't mean nothing to push: the shared clone may hold
        # committed-but-unpushed work — this skill's own or a sibling's (#280).
        # Divergence is a whole-clone property, so we publish the clone's
        # unpushed commits regardless of which skill triggered the push; the
        # floor is "never silently report clean — nothing to push when the
        # clone is ahead of origin".
        div = _clean_divergence(parent_dir, base_ref)
        if div is skill_git.Divergence.UP_TO_DATE:
            click.echo(f"{slug}: clean — nothing to push")
            return
        if div in (skill_git.Divergence.BEHIND, skill_git.Divergence.DIVERGED):
            click.echo(f"{slug}: clean but {div.value} origin — not pushing")
            return
        # AHEAD: publish already-committed work. No commit_paths — the subpath
        # is clean, so there is nothing to stage; we push HEAD as-is.
        if direct:
            skill_git.push(parent_dir, ref=base_ref, env=None)
            entry.local_sha = skill_git.head_sha(parent_dir, env=None)
            write_lock(lock_path, lock)
            click.echo(f"{slug}: pushed (committed-but-unpushed → {base_ref})")
            return
        _push_monorepo_committed_via_pr(parent_dir, slug, base_ref)
        return
    msg = f"skill({slug}): self-improvement {_utc_iso()}"
    if direct:
        skill_git.commit_paths(parent_dir, message=msg, paths=[subpath], env=None)
        skill_git.push(parent_dir, ref=base_ref, env=None)
        entry.local_sha = skill_git.head_sha(parent_dir, env=None)
        write_lock(lock_path, lock)
        click.echo(f"{slug}: pushed (subpath {subpath} → {base_ref})")
        return
    branch = (
        f"skill/self-improvement-{_utc_basic_iso()}-"
        f"{_slug_for_ref(slug)}-{secrets.token_hex(2)}"
    )
    skill_git.checkout_new_branch(parent_dir, name=branch, env=None)
    try:
        skill_git.commit_paths(parent_dir, message=msg, paths=[subpath], env=None)
        skill_git.push(parent_dir, ref=branch, env=None)
        click.echo(f"{slug}: pushed branch {branch}")
        pr_url = _open_pr(parent_dir, branch, base=base_ref, slug=slug)
        if pr_url:
            click.echo(f"  PR: {pr_url}")
        else:
            web = _branch_web_url(parent_dir, branch)
            if web:
                click.echo(f"  → open a PR: {web}")
    finally:
        # Restore the SHARED clone to base. Use a PLAIN checkout, not `-f`:
        # git carries a sibling subpath's uncommitted edits across the switch
        # unharmed, and `-f` would silently DISCARD that in-progress sibling
        # work on every push — the exact multi-skill-in-one-monorepo workflow
        # this feature exists for. In the rare case a sibling's state makes the
        # switch refuse, the GitError propagates to the per-slug handler in
        # push_cmd (the clone may stay on the PR branch, recoverable by hand)
        # rather than destroying unpushed sibling edits.
        skill_git.checkout(parent_dir, ref=base_ref, env=None)


def _push_monorepo_committed_via_pr(
    parent_dir: Path, slug: str, base_ref: str,
) -> None:
    """Open a PR for an owned-monorepo clone's already-committed work (#280).

    Branches at the clone's current HEAD (which carries the ahead commits) and
    pushes that branch — no `commit_paths`, the subpath is clean. The shared
    clone is restored to base with the same PLAIN-checkout discipline as
    `_push_monorepo` so a dirty sibling subpath's in-progress edit survives.
    """
    branch = (
        f"skill/self-improvement-{_utc_basic_iso()}-"
        f"{_slug_for_ref(slug)}-{secrets.token_hex(2)}"
    )
    skill_git.checkout_new_branch(parent_dir, name=branch, env=None)
    try:
        skill_git.push(parent_dir, ref=branch, env=None)
        click.echo(f"{slug}: pushed branch {branch}")
        pr_url = _open_pr(parent_dir, branch, base=base_ref, slug=slug)
        if pr_url:
            click.echo(f"  PR: {pr_url}")
        else:
            web = _branch_web_url(parent_dir, branch)
            if web:
                click.echo(f"  → open a PR: {web}")
    finally:
        # Plain checkout, not `-f` — preserve a dirty sibling subpath's edits
        # (same rationale as `_push_monorepo`'s restore).
        skill_git.checkout(parent_dir, ref=base_ref, env=None)


_REF_SAFE_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def _slug_for_ref(slug: str) -> str:
    """Lower-case the slug and collapse anything outside `[a-zA-Z0-9._-]`
    to a single `-`, so the result is safe to drop into a git ref name."""
    cleaned = _REF_SAFE_RE.sub("-", slug.lower()).strip("-")
    return cleaned or "skill"


def _utc_basic_iso() -> str:
    return _dt.datetime.now(_dt.UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


@functools.lru_cache(maxsize=1)
def _gh_available() -> bool:
    if shutil.which("gh") is None:
        return False
    try:
        proc = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True,
        )
    except OSError:
        return False
    return proc.returncode == 0


def _open_pr(canonical: Path, branch: str, *, base: str, slug: str) -> str | None:
    if not _gh_available():
        return None
    title = f"skill({slug}): self-improvement"
    body = (
        f"Automated self-improvement push from agent-toolkit-cli.\n\n"
        f"Slug: `{slug}`\n"
        f"Branch: `{branch}` → `{base}`\n"
    )
    try:
        proc = subprocess.run(
            [
                "gh", "pr", "create",
                "--base", base,
                "--head", branch,
                "--title", title,
                "--body", body,
            ],
            cwd=str(canonical),
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return _first_url(proc.stdout)


_URL_RE = re.compile(r"https?://\S+")


def _first_url(text: str) -> str | None:
    m = _URL_RE.search(text)
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
