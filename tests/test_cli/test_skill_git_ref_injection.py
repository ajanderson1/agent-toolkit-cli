"""Security: git argument-injection via a dash-prefixed ref (#434).

A ref like `--upload-pack=<cmd>` reaching a git sink as a bare positional
argument is interpreted by git as an *option*, and over local (`file://`) and
`ssh://` transports git executes `<cmd>`. The ref enters the system three ways
— the `/tree/<ref>` URL parser, the `--ref` CLI flag, and a (possibly hostile)
lock file — and only the `owner/repo@ref` shorthand parser previously ran
`_sanitize_ref`. These tests assert the sink layer itself rejects a malicious
ref, so every entry point is covered regardless of which parser fed it.
"""
from pathlib import Path

import pytest

from agent_toolkit_cli.skill_git import (
    GitError,
    clone,
    fetch_ref,
    merge,
    pull_ff_only,
    reset_hard,
)


def test_fetch_ref_upload_pack_injection_does_not_execute(
    git_sandbox, tmp_path: Path,
):
    """The actual exploit: `fetch_ref(ref="--upload-pack=touch PWNED")` against
    a file:// origin must NOT create the marker file. Pre-fix, git ran the
    payload; post-fix the ref is rejected before reaching git."""
    marker = tmp_path / "PWNED"
    payload = f"--upload-pack=touch {marker}"

    with pytest.raises(GitError):
        fetch_ref(git_sandbox.clone, ref=payload, env=git_sandbox.env)

    assert not marker.exists(), (
        "argument injection executed: the --upload-pack payload ran"
    )


def test_clone_rejects_dash_prefixed_ref(git_sandbox, tmp_path: Path):
    payload = f"--upload-pack=touch {tmp_path / 'PWNED'}"
    with pytest.raises(GitError):
        clone(
            f"file://{git_sandbox.upstream}", tmp_path / "out",
            ref=payload, env=git_sandbox.env,
        )
    assert not (tmp_path / "PWNED").exists()


def test_reset_hard_rejects_dash_prefixed_ref(git_sandbox):
    with pytest.raises(GitError):
        reset_hard(git_sandbox.clone, ref="--evil", env=git_sandbox.env)


def test_merge_rejects_dash_prefixed_ref(git_sandbox):
    with pytest.raises(GitError):
        merge(git_sandbox.clone, ref="--evil", env=git_sandbox.env)


def test_pull_ff_only_rejects_dash_prefixed_ref(git_sandbox):
    with pytest.raises(GitError):
        pull_ff_only(git_sandbox.clone, ref="--evil", env=git_sandbox.env)


def test_fetch_ref_accepts_legitimate_ref(git_sandbox):
    """The guard must not break the normal path — fetching a real branch
    still works."""
    # main exists on the sandbox upstream; this must not raise.
    fetch_ref(git_sandbox.clone, ref="main", env=git_sandbox.env)
