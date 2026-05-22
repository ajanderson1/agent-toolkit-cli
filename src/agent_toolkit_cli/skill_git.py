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


@dataclass
class GitResult:
    stdout: str
    stderr: str


_IDENTITY_ALLOWLIST = {
    "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
}


def _scrub(env: dict[str, str] | None) -> dict[str, str]:
    base = dict(env) if env is not None else os.environ.copy()
    return {
        k: v for k, v in base.items()
        if not k.startswith("GIT_") or k in _IDENTITY_ALLOWLIST
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
    url: str, dest: Path, *, ref: str | None, env: dict[str, str] | None
) -> GitResult:
    cmd = ["git", "clone"]
    if ref:
        cmd += ["--branch", ref]
    cmd += [url, str(dest)]
    proc = _run(cmd, env=env)
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def fetch(repo: Path, *, env: dict[str, str] | None) -> GitResult:
    proc = _run(
        ["git", "-C", str(repo), "fetch", "origin", "--prune"], env=env,
    )
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
