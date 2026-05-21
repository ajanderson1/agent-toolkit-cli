import subprocess
from pathlib import Path

import pytest

from agent_toolkit_cli.skill_git import (
    GitError,
    GitWorkingTreeStatus,
    clone,
    fetch,
    head_sha,
    merge,
    push,
    remote_head_sha,
    status,
)


def test_clone_creates_working_tree(git_sandbox, tmp_path: Path):
    dest = tmp_path / "skill-out"
    clone(str(git_sandbox.upstream), dest, ref=None, env=git_sandbox.env)
    assert (dest / ".git").is_dir()
    assert (dest / "SKILL.md").exists()


def test_clone_failure_raises(tmp_path: Path):
    with pytest.raises(GitError):
        clone("file:///nonexistent.git", tmp_path / "x", ref=None, env={})


def test_status_clean(git_sandbox):
    s = status(git_sandbox.clone, env=git_sandbox.env)
    assert s == GitWorkingTreeStatus.CLEAN


def test_status_dirty(git_sandbox):
    (git_sandbox.clone / "SKILL.md").write_text("changed\n")
    s = status(git_sandbox.clone, env=git_sandbox.env)
    assert s == GitWorkingTreeStatus.DIRTY


def test_head_sha_returns_40_char_hex(git_sandbox):
    sha = head_sha(git_sandbox.clone, env=git_sandbox.env)
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


def test_remote_head_sha_matches_head_initially(git_sandbox):
    fetch(git_sandbox.clone, env=git_sandbox.env)
    assert remote_head_sha(
        git_sandbox.clone, ref="main", env=git_sandbox.env
    ) == head_sha(git_sandbox.clone, env=git_sandbox.env)


def test_merge_fast_forwards_when_clean(git_sandbox):
    other = git_sandbox.upstream.parent / "other"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (other / "NEW.md").write_text("new file\n")
    subprocess.run(
        ["git", "-C", str(other), "add", "NEW.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(other), "commit", "-m", "advance"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(other), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    fetch(git_sandbox.clone, env=git_sandbox.env)
    merge(git_sandbox.clone, ref="main", env=git_sandbox.env)
    assert (git_sandbox.clone / "NEW.md").exists()


def test_push_pushes_local_commit(git_sandbox):
    (git_sandbox.clone / "LOCAL.md").write_text("self-improvement\n")
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "add", "LOCAL.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "commit", "-m", "local"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    push(git_sandbox.clone, ref="main", env=git_sandbox.env)
    other = git_sandbox.upstream.parent / "verify"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(other)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    assert (other / "LOCAL.md").exists()


def test_env_with_outer_git_dir_is_scrubbed(git_sandbox, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/tmp/wrong")
    import os
    merged_env = os.environ.copy() | git_sandbox.env
    s = status(git_sandbox.clone, env=merged_env)
    assert s == GitWorkingTreeStatus.CLEAN
