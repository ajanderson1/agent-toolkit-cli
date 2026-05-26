"""Integration: state-builder fixtures produce the divergence state they name."""
import pytest

from agent_toolkit_cli.skill_git import (
    Divergence,
    GitError,
    GitWorkingTreeStatus,
    divergence,
    fetch,
    merge,
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
