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
    reset_hard,
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


def test_is_git_repo_true_for_clone(git_sandbox):
    from agent_toolkit_cli.skill_git import is_git_repo
    assert is_git_repo(git_sandbox.clone) is True


def test_is_git_repo_false_for_plain_dir(tmp_path):
    from agent_toolkit_cli.skill_git import is_git_repo
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "SKILL.md").write_text("hi")
    assert is_git_repo(plain) is False


def test_is_git_repo_false_for_missing(tmp_path):
    from agent_toolkit_cli.skill_git import is_git_repo
    assert is_git_repo(tmp_path / "nope") is False


def test_commit_all_creates_commit_in_target_repo(git_sandbox):
    from agent_toolkit_cli.skill_git import commit_all

    (git_sandbox.clone / "LOCAL.md").write_text("self-improvement\n")
    commit_all(git_sandbox.clone, message="local change", env=git_sandbox.env)

    log = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "log", "-1", "--format=%s"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    )
    assert log.stdout.strip() == "local change"


def test_commit_all_isolation_against_outer_git_dir(
    git_sandbox, tmp_path, monkeypatch,
):
    """Regression: even if a malicious/leaked GIT_DIR is in the caller's env,
    commit_all() must land its commit in the target repo, not the outer one.

    See feedback_git_env_leak.md — this exact failure produced a spurious
    'self-improvement: ...' commit on the worktree's own branch when
    _commit_dirty bypassed _scrub().
    """
    from agent_toolkit_cli.skill_git import commit_all

    # Create a separate "outer" repo to act as the would-be hijack target.
    outer = tmp_path / "outer"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(outer)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (outer / "seed").write_text("seed\n")
    subprocess.run(
        ["git", "-C", str(outer), "add", "seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(outer), "commit", "-m", "outer-seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    outer_head_before = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()

    # Simulate the leaked-env scenario.
    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer / ".git" / "index"))

    (git_sandbox.clone / "LOCAL.md").write_text("self-improvement\n")
    import os
    merged_env = os.environ.copy() | git_sandbox.env
    # Re-leak after the merge to make sure the helper itself scrubs:
    merged_env["GIT_DIR"] = str(outer / ".git")
    merged_env["GIT_INDEX_FILE"] = str(outer / ".git" / "index")

    commit_all(git_sandbox.clone, message="should-land-in-sandbox", env=merged_env)

    sandbox_head_msg = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "log", "-1", "--format=%s"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert sandbox_head_msg == "should-land-in-sandbox"

    outer_head_after = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert outer_head_after == outer_head_before, (
        "GIT_DIR leak landed a commit in the outer repo"
    )


def test_reset_hard_snaps_working_tree_to_origin_ref(git_sandbox, tmp_path):
    """Advance upstream, then reset_hard() must pull the clone forward,
    discarding any local divergence."""
    # Advance upstream via a second clone.
    advancer = tmp_path / "advancer"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(advancer)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (advancer / "NEW.md").write_text("from upstream\n")
    subprocess.run(
        ["git", "-C", str(advancer), "add", "NEW.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(advancer), "commit", "-m", "advance"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(advancer), "push", "origin", "main"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    # Dirty up the clone with a local commit on a divergent path.
    (git_sandbox.clone / "LOCAL.md").write_text("local-divergence\n")
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "add", "LOCAL.md"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "commit", "-m", "local-only"],
        check=True, env=git_sandbox.env, capture_output=True,
    )

    fetch(git_sandbox.clone, env=git_sandbox.env)
    reset_hard(git_sandbox.clone, ref="main", env=git_sandbox.env)

    # Upstream's new file is present; local-only file is gone.
    assert (git_sandbox.clone / "NEW.md").exists()
    assert not (git_sandbox.clone / "LOCAL.md").exists()
    # HEAD now matches origin/main exactly.
    assert head_sha(git_sandbox.clone, env=git_sandbox.env) == remote_head_sha(
        git_sandbox.clone, ref="main", env=git_sandbox.env
    )


def test_reset_hard_isolation_against_outer_git_dir(
    git_sandbox, tmp_path, monkeypatch,
):
    """Regression-style guard: a leaked GIT_DIR / GIT_INDEX_FILE must not
    redirect the hard-reset into the outer repo.

    See feedback_git_env_leak.md — reset_hard() goes through _run() so the
    same scrub fires.
    """
    outer = tmp_path / "outer"
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(outer)],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    (outer / "seed").write_text("seed\n")
    subprocess.run(
        ["git", "-C", str(outer), "add", "seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(outer), "commit", "-m", "outer-seed"],
        check=True, env=git_sandbox.env, capture_output=True,
    )
    outer_head_before = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()

    monkeypatch.setenv("GIT_DIR", str(outer / ".git"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(outer / ".git" / "index"))

    import os
    merged_env = os.environ.copy() | git_sandbox.env
    merged_env["GIT_DIR"] = str(outer / ".git")
    merged_env["GIT_INDEX_FILE"] = str(outer / ".git" / "index")

    fetch(git_sandbox.clone, env=merged_env)
    reset_hard(git_sandbox.clone, ref="main", env=merged_env)

    outer_head_after = subprocess.run(
        ["git", "-C", str(outer), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert outer_head_after == outer_head_before, (
        "GIT_DIR leak caused reset_hard to touch the outer repo"
    )
