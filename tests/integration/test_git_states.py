"""Integration: state-builder fixtures produce the divergence state they name."""
import subprocess

import pytest

from agent_toolkit_cli.skill_git import (
    Divergence,
    GitError,
    GitWorkingTreeStatus,
    divergence,
    fetch,
    head_sha,
    merge,
    push,
    status,
)


def test_make_behind_yields_behind(make_behind):
    sandbox = make_behind
    fetch(sandbox.clone, env=sandbox.env)
    assert divergence(sandbox.clone, ref="main", env=sandbox.env) == Divergence.BEHIND


def test_make_ahead_yields_ahead(make_ahead):
    sandbox = make_ahead
    fetch(sandbox.clone, env=sandbox.env)
    assert divergence(sandbox.clone, ref="main", env=sandbox.env) == Divergence.AHEAD


def test_make_diverged_yields_diverged(make_diverged):
    sandbox = make_diverged
    fetch(sandbox.clone, env=sandbox.env)
    assert divergence(sandbox.clone, ref="main", env=sandbox.env) == Divergence.DIVERGED


def test_make_dirty_yields_dirty(make_dirty):
    sandbox = make_dirty
    assert status(sandbox.clone, env=sandbox.env) == GitWorkingTreeStatus.DIRTY


def test_make_conflict_blocks_merge(make_conflict):
    """Both sides edited the same line — merge must raise GitError."""
    sandbox = make_conflict
    fetch(sandbox.clone, env=sandbox.env)
    with pytest.raises(GitError):
        merge(sandbox.clone, ref="main", env=sandbox.env)


def test_behind_then_merge_fast_forwards(make_behind):
    s = make_behind
    fetch(s.clone, env=s.env)
    before = head_sha(s.clone, env=s.env)
    merge(s.clone, ref="main", env=s.env)
    after = head_sha(s.clone, env=s.env)
    assert before != after  # fast-forwarded to upstream
    assert (s.clone / "UPSTREAM.md").exists()


def test_ahead_merge_is_noop(make_ahead):
    s = make_ahead
    fetch(s.clone, env=s.env)
    before = head_sha(s.clone, env=s.env)
    merge(s.clone, ref="main", env=s.env)  # "Already up to date"
    assert head_sha(s.clone, env=s.env) == before


def test_diverged_merge_creates_merge_commit(make_diverged):
    s = make_diverged
    fetch(s.clone, env=s.env)
    merge(s.clone, ref="main", env=s.env)
    # Merge commit has two parents.
    parents = subprocess.run(
        ["git", "-C", str(s.clone), "rev-list", "--parents", "-n", "1", "HEAD"],
        check=True, env=s.env, capture_output=True, text=True,
    ).stdout.split()
    assert len(parents) == 3  # self + 2 parents


def test_conflict_merge_leaves_recoverable_tree(make_conflict):
    """Documents current behaviour: merge raises, tree is mid-merge but
    `git merge --abort` recovers it. See Gap Ledger §3."""
    s = make_conflict
    fetch(s.clone, env=s.env)
    with pytest.raises(GitError):
        merge(s.clone, ref="main", env=s.env)
    # Recoverable: abort succeeds and returns rc 0.
    abort = subprocess.run(
        ["git", "-C", str(s.clone), "merge", "--abort"],
        env=s.env, capture_output=True,
    )
    assert abort.returncode == 0


def test_ahead_push_succeeds_no_ownership_check(make_ahead):
    """Documents current behaviour: push proceeds whenever git push works —
    there is no upstream-ownership verification. See Gap Ledger §5."""
    s = make_ahead
    push(s.clone, ref="main", env=s.env)
    fetch(s.clone, env=s.env)
    assert divergence(s.clone, ref="main", env=s.env) == Divergence.UP_TO_DATE
