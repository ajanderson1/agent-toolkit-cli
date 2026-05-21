"""Shared fixtures for tests/test_cli/."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass
class GitSandbox:
    upstream: Path     # bare repo acting as the "remote"
    clone: Path        # working clone of upstream, pre-populated
    env: dict[str, str]


def _scrub_git_env(base: dict[str, str]) -> dict[str, str]:
    """Strip inherited GIT_* env vars. See memory feedback_git_env_leak.md."""
    return {k: v for k, v in base.items() if not k.startswith("GIT_")}


@pytest.fixture
def git_sandbox(tmp_path: Path) -> GitSandbox:
    env = _scrub_git_env(os.environ.copy())
    env.update({
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
        "HOME": str(tmp_path / "fake-home"),
    })
    (tmp_path / "fake-home").mkdir()

    upstream = tmp_path / "upstream.git"
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(upstream)],
        check=True, env=env, capture_output=True,
    )

    seed = tmp_path / "seed"
    seed.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main", str(seed)],
        check=True, env=env, capture_output=True,
    )
    (seed / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A test skill.\n---\n# demo\n"
    )
    subprocess.run(
        ["git", "-C", str(seed), "add", "SKILL.md"],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "commit", "-m", "seed"],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "remote", "add", "origin", str(upstream)],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(seed), "push", "origin", "main"],
        check=True, env=env, capture_output=True,
    )

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", str(upstream), str(clone)],
        check=True, env=env, capture_output=True,
    )

    return GitSandbox(upstream=upstream, clone=clone, env=env)
