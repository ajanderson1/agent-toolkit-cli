"""Thin wrapper around `git` subprocess invocations for the skill model.

Scrubs inherited GIT_* env vars before each call (see memory
feedback_git_env_leak.md — leaked GIT_DIR / GIT_INDEX_FILE redirects
commits into a parent repo). Author/committer identity vars are
preserved so tests can pin them.
"""
from __future__ import annotations

import enum
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """Raised when a git invocation fails."""

    def __init__(self, cmd: list[str], result: subprocess.CompletedProcess) -> None:
        super().__init__(
            f"git {cmd!r} failed (rc={result.returncode}):\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
        )
        self.cmd = cmd
        self.returncode = result.returncode
        self.stdout = result.stdout
        self.stderr = result.stderr


class GitWorkingTreeStatus(enum.Enum):
    CLEAN = "clean"
    DIRTY = "dirty"


class Divergence(enum.Enum):
    """Local HEAD relative to origin/<ref>, classified from
    `git rev-list --left-right --count`."""
    UP_TO_DATE = "up_to_date"
    BEHIND = "behind"      # upstream has commits we don't
    AHEAD = "ahead"        # we have commits upstream doesn't
    DIVERGED = "diverged"  # both sides moved


@dataclass
class GitResult:
    stdout: str
    stderr: str


_IDENTITY_ALLOWLIST = {
    "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
}


# GIT_* vars that are safe to carry through the scrub. Unlike GIT_DIR /
# GIT_INDEX_FILE these cannot redirect commits into a parent repo — they only
# govern how git talks to a remote (whether it may prompt for credentials and
# which ssh command to use). `clone()` sets them to fail loudly instead of
# hanging on a missing credential (#251).
_CLONE_PASSTHROUGH = {"GIT_TERMINAL_PROMPT", "GIT_SSH_COMMAND"}


def _scrub(env: dict[str, str] | None) -> dict[str, str]:
    base = dict(env) if env is not None else os.environ.copy()
    return {
        k: v for k, v in base.items()
        if not k.startswith("GIT_")
        or k in _IDENTITY_ALLOWLIST
        or k in _CLONE_PASSTHROUGH
    }


def _run(
    cmd: list[str], *, env: dict[str, str] | None
) -> subprocess.CompletedProcess:
    scrubbed = _scrub(env)
    proc = subprocess.run(
        cmd, env=scrubbed, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise GitError(cmd, proc)
    return proc


def clone(
    url: str, dest: Path, *, ref: str | None, env: dict[str, str] | None,
    depth: int | None = None,
) -> GitResult:
    """Clone `url` into `dest`, failing loudly rather than hanging.

    Forces `GIT_TERMINAL_PROMPT=0` so a missing HTTPS credential helper makes
    git exit non-zero (raising `GitError`) instead of blocking on an
    interactive `Username for 'https://...'` prompt — the hang that bit a
    fresh SSH-only host (#251). For the SSH transport we default
    `GIT_SSH_COMMAND` to BatchMode so a missing key / unknown host fails the
    same way; a caller-supplied `GIT_SSH_COMMAND` is respected.

    `depth` (when set) passes `--depth <n>` for a shallow clone — used by
    `skill import` to avoid transferring a fat monorepo's full history when
    only one commit's tree is ever needed (#259). Defaults to `None` (full
    clone) so every other caller is unchanged. A shallow clone has only the
    cloned ref's tree; callers that then check out an *older* pinned commit
    must `fetch_ref()` it first.
    """
    cmd = ["git", "clone"]
    if depth is not None:
        cmd += ["--depth", str(depth)]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(dest)]
    clone_env = dict(env) if env is not None else os.environ.copy()
    clone_env["GIT_TERMINAL_PROMPT"] = "0"
    clone_env.setdefault("GIT_SSH_COMMAND", "ssh -o BatchMode=yes")
    proc = _run(cmd, env=clone_env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def fetch(repo: Path, *, env: dict[str, str] | None) -> GitResult:
    proc = _run(
        ["git", "-C", str(repo), "fetch", "origin", "--prune"], env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def fetch_ref(
    repo: Path, *, ref: str, env: dict[str, str] | None,
    depth: int | None = None,
) -> GitResult:
    """Fetch a single `ref` (branch, tag, or full SHA) into `repo`.

    Distinct from `fetch()` (which does `fetch origin --prune` for all refs):
    this pulls exactly one ref, optionally shallow via `--depth`. Used by the
    `skill import` shallow path — a depth-1 clone holds only the cloned ref's
    tree, so the pinned commit must be fetched before it can be checked out
    (#259). Fetching a SHA requires the remote to allow SHA-in-want (GitHub
    does). Goes through `_run` so GIT_* env vars are scrubbed identically to
    every other git call (see memory feedback_git_env_leak.md).
    """
    cmd = ["git", "-C", str(repo), "fetch"]
    if depth is not None:
        cmd += ["--depth", str(depth)]
    cmd += ["origin", ref]
    proc = _run(cmd, env=env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


_DEFAULT_IDENTITY = (
    "-c", "user.name=agent-toolkit-cli",
    "-c", "user.email=noreply@agent-toolkit-cli",
)


def merge(repo: Path, *, ref: str, env: dict[str, str] | None) -> GitResult:
    """Merge `origin/<ref>` into the current branch.

    Pins a synthetic `user.name`/`user.email` via `-c` so the merge commit
    can be created without relying on the host's global git config — agents,
    CI runners, and fresh dev VMs often have no identity configured. The
    same constant is reused by `commit_all()`. Callers that need to
    override (tests, future per-user flows) can still inject
    `GIT_AUTHOR_*` / `GIT_COMMITTER_*` env vars, which take precedence over
    `-c` config values.
    """
    proc = _run(
        ["git", "-C", str(repo), *_DEFAULT_IDENTITY,
         "merge", "--no-edit", f"origin/{ref}"],
        env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def reset_hard(
    repo: Path, *, ref: str, env: dict[str, str] | None,
) -> GitResult:
    """Hard-reset `repo`'s working tree to `origin/<ref>`.

    Discards local commits and uncommitted changes. Goes through `_run` so
    GIT_* env vars are scrubbed identically to every other git call
    (see memory feedback_git_env_leak.md — a leaked GIT_DIR / GIT_INDEX_FILE
    would otherwise redirect the operation into the parent repo).
    """
    proc = _run(
        ["git", "-C", str(repo), "reset", "--hard", f"origin/{ref}"],
        env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def pull_ff_only(
    repo: Path, *, ref: str, env: dict[str, str] | None,
) -> GitResult:
    """`git pull --ff-only origin <ref>` for monorepo-parent refresh.

    Same env scrubbing as the other helpers in this module. Raises GitError
    when the remote can't be fast-forwarded (e.g. divergent history) — the
    caller surfaces that as a conflict to the user.
    """
    proc = _run(
        ["git", "-C", str(repo), "pull", "--ff-only", "origin", ref],
        env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def is_git_repo(repo: Path) -> bool:
    """True when `repo` contains a git working tree (`.git` directory or
    git-dir file). False for missing paths or plain file trees.

    Useful for skills installed via `npx skills add --copy`, which lays
    down plain files without a `.git/` — operations like `status` and
    `update` are not applicable to those installs.
    """
    if not repo.is_dir():
        return False
    git_dir = repo / ".git"
    return git_dir.is_dir() or git_dir.is_file()


def status(repo: Path, *, env: dict[str, str] | None) -> GitWorkingTreeStatus:
    proc = _run(["git", "-C", str(repo), "status", "--porcelain"], env=env)
    return (
        GitWorkingTreeStatus.CLEAN if not proc.stdout.strip()
        else GitWorkingTreeStatus.DIRTY
    )


def push(repo: Path, *, ref: str, env: dict[str, str] | None) -> GitResult:
    proc = _run(["git", "-C", str(repo), "push", "origin", ref], env=env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def checkout_new_branch(
    repo: Path, *, name: str, env: dict[str, str] | None,
) -> GitResult:
    """`git checkout -b <name>` from the current HEAD."""
    proc = _run(
        ["git", "-C", str(repo), "checkout", "-b", name], env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def checkout(repo: Path, *, ref: str, env: dict[str, str] | None) -> GitResult:
    """`git checkout <ref>`. Caller owns ensuring the working tree is in a
    state that can accept the switch (e.g. has just committed)."""
    proc = _run(
        ["git", "-C", str(repo), "checkout", ref], env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def current_branch(repo: Path, *, env: dict[str, str] | None) -> str:
    proc = _run(
        ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
        env=env,
    )
    return proc.stdout.strip()


def remote_url(repo: Path, *, env: dict[str, str] | None) -> str:
    proc = _run(
        ["git", "-C", str(repo), "remote", "get-url", "origin"], env=env,
    )
    return proc.stdout.strip()


def commit_all(
    repo: Path, *, message: str, env: dict[str, str] | None,
) -> GitResult:
    """Stage every working-tree change and commit. Goes through _run so env
    is scrubbed identically to every other git call — never spawn `git` from
    the command layer directly (see memory feedback_git_env_leak.md).

    Pins the same synthetic identity as `merge()` via `*_DEFAULT_IDENTITY`
    so the commit succeeds on hosts without a global git config (CI
    runners, fresh dev VMs, agent sandboxes). `GIT_AUTHOR_*` /
    `GIT_COMMITTER_*` env vars still take precedence per git's config rules.
    """
    _run(["git", "-C", str(repo), "add", "-A"], env=env)
    proc = _run(
        ["git", "-C", str(repo), *_DEFAULT_IDENTITY,
         "commit", "-m", message],
        env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def status_path(
    repo: Path, path: str, *, env: dict[str, str] | None,
) -> GitWorkingTreeStatus:
    """Working-tree status scoped to a pathspec within `repo`.

    `git status --porcelain -- <path>` — used so an owned-monorepo skill's
    dirty state reflects only its own subpath, not sibling skills sharing the
    parent clone. Goes through _run so GIT_* env is scrubbed (the #209 trap).
    """
    proc = _run(
        ["git", "-C", str(repo), "status", "--porcelain", "--", path],
        env=env,
    )
    return (
        GitWorkingTreeStatus.CLEAN if not proc.stdout.strip()
        else GitWorkingTreeStatus.DIRTY
    )


def commit_paths(
    repo: Path, *, message: str, paths: list[str], env: dict[str, str] | None,
) -> bool:
    """Stage + commit ONLY `paths` within `repo`. Returns True if a commit was
    made, False if nothing under `paths` was staged (clean subpath).

    `git add -- <paths>` then `git commit -- <paths>`. The trailing pathspec on
    commit keeps the commit scoped even if other parts of the tree are dirty —
    the mechanism that isolates an owned-monorepo skill's push to its own
    subpath. Pins the same synthetic identity as `commit_all()`/`merge()`.
    Goes through _run so GIT_* env is scrubbed (the #209 trap).
    """
    _run(["git", "-C", str(repo), "add", "--", *paths], env=env)
    # Detect whether anything is staged under the pathspec; if not, no-op.
    staged = subprocess.run(
        ["git", "-C", str(repo), "diff", "--cached", "--quiet", "--", *paths],
        env=_scrub(env), capture_output=True, text=True,
    )
    if staged.returncode == 0:
        return False  # nothing staged under the pathspec
    _run(
        ["git", "-C", str(repo), *_DEFAULT_IDENTITY,
         "commit", "-m", message, "--", *paths],
        env=env,
    )
    return True


def head_sha(repo: Path, *, env: dict[str, str] | None) -> str:
    proc = _run(["git", "-C", str(repo), "rev-parse", "HEAD"], env=env)
    return proc.stdout.strip()


def remote_head_sha(
    repo: Path, *, ref: str, env: dict[str, str] | None
) -> str:
    proc = _run(
        ["git", "-C", str(repo), "rev-parse", f"origin/{ref}"], env=env,
    )
    return proc.stdout.strip()


def divergence(
    repo: Path, *, ref: str, env: dict[str, str] | None
) -> Divergence:
    """Classify local HEAD vs origin/<ref> using
    `git rev-list --left-right --count HEAD...origin/<ref>`, which prints
    `<ahead>\\t<behind>`.

    Reads ONLY the local repo's refs — it does NOT fetch. Callers that need
    a live comparison must `fetch()` first; otherwise origin/<ref> is
    whatever the last fetch/clone recorded.
    """
    proc = _run(
        ["git", "-C", str(repo), "rev-list", "--left-right", "--count",
         f"HEAD...origin/{ref}"],
        env=env,
    )
    ahead_str, behind_str = proc.stdout.split()
    ahead, behind = int(ahead_str), int(behind_str)
    if ahead and behind:
        return Divergence.DIVERGED
    if ahead:
        return Divergence.AHEAD
    if behind:
        return Divergence.BEHIND
    return Divergence.UP_TO_DATE
