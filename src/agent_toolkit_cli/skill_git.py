"""Thin wrapper around `git` subprocess invocations for the skill model.

Scrubs inherited GIT_* env vars before each call (see memory
feedback_git_env_leak.md — leaked GIT_DIR / GIT_INDEX_FILE redirects
commits into a parent repo). Author/committer identity vars are
preserved so tests can pin them.
"""
from __future__ import annotations

import enum
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from agent_toolkit_cli.skill_lock import looks_like_sha
from agent_toolkit_cli.skill_source import SourceParseError, sanitize_ref


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


class UnsafeRefError(GitError):
    """A ref was rejected before reaching git because it could be misread as a
    command-line option (security: #434). Subclasses GitError so the sinks'
    existing `except GitError` handlers and callers cover it unchanged."""

    def __init__(self, ref: str, reason: str) -> None:
        # Bypass GitError.__init__ (which needs a CompletedProcess); set the
        # same public attributes so callers that read .stderr / .returncode
        # still work.
        RuntimeError.__init__(self, f"Unsafe git ref {ref!r}: {reason}")
        self.cmd = ["git", "<ref-guard>", ref]
        self.returncode = -1
        self.stdout = ""
        self.stderr = reason


def _guard_ref(ref: str) -> str:
    """Reject a ref that git could misread as an *option* before it reaches a
    subprocess argument (security: #434).

    The sink layer is the chokepoint every ref passes through regardless of
    which parser produced it — the `/tree/<ref>` URL parser, the `--ref` CLI
    flag, or a hostile lock file. A dash-prefixed ref like `--upload-pack=<cmd>`
    handed to `git clone --branch <ref>` / `git fetch origin <ref>` as a
    positional is executed by git over `file://` and `ssh://` transports. We
    reuse `skill_source.sanitize_ref` (one source of truth for the rules) and
    re-raise its `SourceParseError` as `UnsafeRefError`, a `GitError` subclass
    this layer's callers already handle.
    """
    try:
        return sanitize_ref(ref)
    except SourceParseError as exc:
        raise UnsafeRefError(ref, str(exc)) from exc


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
        cmd += ["--branch", _guard_ref(ref)]
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
    cmd += ["origin", _guard_ref(ref)]
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
         "merge", "--no-edit", f"origin/{_guard_ref(ref)}"],
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
        ["git", "-C", str(repo), "reset", "--hard", f"origin/{_guard_ref(ref)}"],
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
        ["git", "-C", str(repo), "pull", "--ff-only", "origin", _guard_ref(ref)],
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
    proc = _run(
        ["git", "-C", str(repo), "push", "origin", _guard_ref(ref)], env=env,
    )
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
        ["git", "-C", str(repo), "checkout", _guard_ref(ref)], env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)


def clone_pinned_or_branch(
    url: str, dest: Path, *, ref: str | None, env: dict[str, str] | None,
) -> None:
    """Clone `url` into `dest`, honouring a possible SHA pin.

    `git clone --branch <sha>` is rejected by git, so a SHA `ref` is applied
    post-clone: clone at HEAD (ref=None), best-effort fetch_ref (rescues
    full-SHA wants not reachable from advertised tips; always fails for
    abbreviations, which checkout resolves locally), then checkout as the
    fail-loud authority. A branch/tag `ref` (or None → remote default) clones
    `--branch` directly. A failed checkout removes the partial clone and
    re-raises — fail loud, no orphan dir (#313, #345).

    Takes a raw `ref`, not a LockEntry, and derives the pin via bare
    `looks_like_sha` (NOT is_sha_pinned): every clone site holds a store-owned
    source — npm entries are never cloned — so the source_type gate is moot
    here. This is the one place bare `looks_like_sha` is correct over the
    origin-aware property.
    """
    pin = ref if looks_like_sha(ref) else None
    clone(url, dest, ref=None if pin else ref, env=env)
    if pin and is_git_repo(dest):
        try:
            fetch_ref(dest, ref=pin, env=env)
        except GitError:
            pass  # best-effort; checkout resolves locally
        try:
            checkout(dest, ref=pin, env=env)
        except GitError:
            shutil.rmtree(dest, ignore_errors=True)
            raise


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


_SSH_GIT_URL_RE = re.compile(r"^git@([^:]+):(.+?)(?:\.git)?/?$")
_HTTPS_GIT_URL_RE = re.compile(r"^https?://([^/]+)/(.+?)(?:\.git)?/?$")
_SSH_URL_RE = re.compile(r"^ssh://(?:[^@]+@)?([^/]+)/(.+?)(?:\.git)?/?$")


def normalise_git_url(url: str) -> str:
    """Reduce SSH and HTTPS forms to ``host/path`` for equality comparison.

    `git@github.com:foo/bar.git` and `https://github.com/foo/bar.git` both
    collapse to `github.com/foo/bar`. Trailing slashes and the `ssh://` URL
    form are also folded in. Anything that doesn't match any pattern falls
    back to lowercase + trailing-`.git` strip + trailing-slash strip, so
    local paths and unfamiliar URL forms still round-trip sensibly.
    """
    u = url.strip().lower()
    if (m := _SSH_GIT_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if (m := _HTTPS_GIT_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    if (m := _SSH_URL_RE.match(u)):
        return f"{m.group(1)}/{m.group(2)}"
    u = u.rstrip("/")
    if u.endswith(".git"):
        u = u[:-4]
    return u


def remote_matches(
    repo: Path, parent_url: str | None, env: dict[str, str] | None,
) -> bool:
    """True if `repo`'s origin remote names the same repo as `parent_url`.

    Compares normalised (SSH/HTTPS-folded) forms so `git@…:o/r.git` and
    `https://…/o/r` are treated as equal. A repo with no origin (or any git
    error reading it) is treated as a non-match. A `parent_url` of None is also
    a non-match: with no expected URL there is nothing to match against, so the
    predicate fails safe rather than crashing in `normalise_git_url(None)`
    (every current caller already gates on a non-None parent_url, but this keeps
    a future caller that forgets the gate from raising mid-resolve).
    """
    if parent_url is None:
        return False
    try:
        actual = remote_url(repo, env=env)
    except GitError:
        return False
    return normalise_git_url(actual) == normalise_git_url(parent_url)


def _checked_out_at_ref(bare: Path, ref: str, env: dict[str, str] | None) -> bool:
    """True if the bare clone is actually at `ref`.

    Multi-ref safety (#412): several skills can share one monorepo at DIFFERENT
    refs, but a single clone is checked out at exactly ONE ref. Adopting a bare
    clone for a skill whose ref it is NOT on would let `update`/`reset` mutate or
    discard the tree the other skill depends on. So the ref must match:

    - SHA pin (`looks_like_sha`): the clone is detached at a commit, so
      `current_branch` returns ``"HEAD"`` — compare HEAD's sha (prefix match,
      honouring abbreviated pins). **But** `looks_like_sha` also matches a branch
      literally NAMED with a hex string (e.g. ``dead123``); such a clone is on a
      branch (not detached), so the SHA arm fails and we fall through to an exact
      branch-name comparison. The SHA-shaped ref therefore matches on EITHER the
      commit prefix OR an exact branch name (#422 fix 1).
    - Branch ref (non-hex): require the checked-out branch to equal `ref`.

    Accepted residuals (both astronomically unlikely — require a user-authored
    7-40 char hex collision):
      (a) two SHA pins whose abbreviations collide (pre-existing);
      (b) an abbreviated-SHA `ref` string that is ALSO a sibling skill's
          checked-out branch name — the branch arm then adopts the sibling's
          clone for the SHA-pinned skill. Same class as (a); the branch arm only
          fires on a genuinely hex-named branch (a true SHA pin is detached, so
          `current_branch` returns ``"HEAD"`` which never equals a lowercase-hex
          ref). This widening fixes the reachable hex-named-branch false-refuse;
          (b) is the documented cost.

    Any git error reading the clone is treated as "does not match" (fail safe).
    """
    try:
        if looks_like_sha(ref):
            if head_sha(bare, env=env).startswith(ref):
                return True
            # hex-NAMED branch: clone is on a branch, not detached at a commit.
            return current_branch(bare, env=env) == ref
        return current_branch(bare, env=env) == ref
    except GitError:
        return False


def legacy_bare_clone_for(
    suffixed: Path, bare: Path, *, ref: str | None, parent_url: str | None,
    env: dict[str, str] | None,
) -> Path | None:
    """Return `bare` iff it is the legacy bare-named clone for this skill (#412).

    A monorepo parent cloned before its lock `ref` was backfilled (None -> main)
    lives at the flat `<repo>` path instead of the canonical `<repo>@<ref>`.
    Both the read-path resolver (`skill_paths.resolve_existing_parent_clone`) and
    doctor's `legacy_bare_parent` finding need the SAME test for "is this bare
    dir ours?", so it lives here once and both consume it — they cannot drift.

    All of the following must hold to adopt the bare clone:

    - `ref` is set (a None ref already lives at the bare path — nothing to alias).
    - `bare.parent == suffixed.parent` — the bare/suffixed pair are siblings only
      for a FLAT ref. A slash ref makes `<repo>@feat/x` a two-component path, so
      `Path.parent` is `…/<repo>@feat` (not `…/<owner>/`), differing from bare
      `<repo>`'s parent `…/<owner>/`. The equality therefore holds ONLY for flat
      refs; a flat bare `<repo>` is then a DIFFERENT skill's clone and is
      excluded. (This is `Path` component parsing, not physical dir nesting.)
    - `bare` is a git repo whose origin remote matches `parent_url`.
    - `bare` is actually checked out at `ref` (see `_checked_out_at_ref`).

    Returns None when any condition fails, so callers fall back to the canonical
    suffixed path.
    """
    if ref is None:
        return None
    if (
        bare.parent == suffixed.parent
        and is_git_repo(bare)
        and remote_matches(bare, parent_url, env)
        and _checked_out_at_ref(bare, ref, env)
    ):
        return bare
    return None


def default_branch(repo: Path, *, env: dict[str, str] | None) -> str | None:
    """Best-effort detection of origin's default branch (e.g. `main`,
    `master`).

    Reads `git symbolic-ref refs/remotes/origin/HEAD`, which a normal `clone`
    sets to track the remote's HEAD. When that ref is missing (some shallow or
    mirror clones don't populate it) we ask git to recompute it via
    `git remote set-head origin --auto` and re-read. Returns the bare branch
    name, or `None` if it still can't be determined — callers fall back to
    their own default rather than guessing `main`, which silently broke every
    `master`-based upstream (the upstash/context7 trap).
    """
    def _read() -> str | None:
        try:
            proc = _run(
                ["git", "-C", str(repo), "symbolic-ref",
                 "refs/remotes/origin/HEAD"],
                env=env,
            )
        except GitError:
            return None
        ref = proc.stdout.strip()
        prefix = "refs/remotes/origin/"
        return ref[len(prefix):] if ref.startswith(prefix) else None

    branch = _read()
    if branch is not None:
        return branch
    # origin/HEAD not set — ask git to recompute it from the remote, then retry.
    try:
        _run(
            ["git", "-C", str(repo), "remote", "set-head", "origin", "--auto"],
            env=env,
        )
    except GitError:
        return None
    return _read()


def resolve_ref(
    ref: str | None, repo: Path | None, *, env: dict[str, str] | None = None,
) -> str:
    """The branch to operate against: an explicit `ref`, else the upstream's
    detected default branch, else `"main"`.

    Centralises the fix for the assumption that every upstream's default branch
    is `main` — which silently broke every `master`-based repo such as
    upstash/context7 (`merge: origin/main - not something we can merge`). When
    `ref` is None and `repo` is a real clone, we read the clone's
    `origin/HEAD`; only if that can't be determined do we fall back to `"main"`,
    preserving prior behaviour for `main` repos and for callers with no clone
    yet. Takes the bare ref value (not a lock entry) so both `entry.ref` and
    parse-time `parsed.ref` callers, across every asset type, share one path.
    `env` is threaded to the detection git calls for callers that run under a
    custom environment (the install engines).
    """
    if ref:
        return ref
    if repo is not None and is_git_repo(repo):
        detected = default_branch(repo, env=env)
        if detected:
            return detected
    return "main"


def diff_shortstat(
    repo: Path, *, base: str, head: str, env: dict[str, str] | None
) -> tuple[int, int, int]:
    """Return `(files_changed, insertions, deletions)` between two commits.

    Parses `git diff --shortstat <base> <head>`. An empty diff (no movement)
    returns `(0, 0, 0)`. Used by `skill update` to print a one-line change
    summary so a refresh shows what actually moved instead of a bare
    `updated`. Goes through `_run` so GIT_* env is scrubbed like every other
    call.
    """
    proc = _run(
        ["git", "-C", str(repo), "diff", "--shortstat", base, head], env=env,
    )
    text = proc.stdout.strip()
    if not text:
        return (0, 0, 0)
    files = insertions = deletions = 0
    for chunk in text.split(","):
        chunk = chunk.strip()
        n = int(chunk.split()[0])
        if "file" in chunk:
            files = n
        elif "insertion" in chunk:
            insertions = n
        elif "deletion" in chunk:
            deletions = n
    return (files, insertions, deletions)


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
