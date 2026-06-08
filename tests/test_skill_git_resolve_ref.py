"""Unit tests for the default-branch detection that the `*.ref or "main"`
fix relies on.

`resolve_ref` / `default_branch` are kind-agnostic — every asset kind (skill,
agent, pi_extension) routes its ref resolution through them, so covering them
here covers the master-default fix for all kinds without duplicating each CLI
round-trip. The regression these guard: a `master`-default upstream (e.g.
upstash/context7) used to merge against the nonexistent `origin/main`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from agent_toolkit_cli import skill_git

from tests.conftest import scrub_git_env


def _clone_with_default(tmp_path: Path, *, branch: str) -> Path:
    """A clone whose origin default branch is `branch`."""
    env = scrub_git_env()
    upstream = tmp_path / f"upstream-{branch}.git"
    subprocess.run(
        ["git", "init", "--bare", f"--initial-branch={branch}", str(upstream)],
        check=True, env=env, capture_output=True,
    )
    seed = tmp_path / f"seed-{branch}"
    subprocess.run(
        ["git", "init", f"--initial-branch={branch}", str(seed)],
        check=True, env=env, capture_output=True,
    )
    (seed / "f.txt").write_text("x\n")
    for cmd in (
        ["git", "-C", str(seed), "add", "."],
        ["git", "-C", str(seed), "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-m", "seed"],
        ["git", "-C", str(seed), "remote", "add", "origin", str(upstream)],
        ["git", "-C", str(seed), "push", "origin", branch],
    ):
        subprocess.run(cmd, check=True, env=env, capture_output=True)
    clone = tmp_path / f"clone-{branch}"
    subprocess.run(
        ["git", "clone", str(upstream), str(clone)],
        check=True, env=env, capture_output=True,
    )
    return clone


def test_default_branch_detects_master(tmp_path):
    clone = _clone_with_default(tmp_path, branch="master")
    assert skill_git.default_branch(clone, env=None) == "master"


def test_default_branch_detects_main(tmp_path):
    clone = _clone_with_default(tmp_path, branch="main")
    assert skill_git.default_branch(clone, env=None) == "main"


def test_resolve_ref_explicit_wins(tmp_path):
    """An explicit ref always wins — detection is never consulted."""
    clone = _clone_with_default(tmp_path, branch="master")
    assert skill_git.resolve_ref("v2.1.0", clone) == "v2.1.0"


def test_resolve_ref_detects_master_when_unpinned(tmp_path):
    clone = _clone_with_default(tmp_path, branch="master")
    assert skill_git.resolve_ref(None, clone) == "master"


def test_resolve_ref_falls_back_to_main_without_repo(tmp_path):
    """No clone to detect from (e.g. a clone-time caller) → legacy `main`."""
    assert skill_git.resolve_ref(None, tmp_path / "does-not-exist") == "main"
    assert skill_git.resolve_ref(None, None) == "main"


def test_default_branch_recomputes_when_origin_head_unset(tmp_path):
    """Some clones have no `origin/HEAD`; detection must recompute it via
    `remote set-head --auto` rather than giving up. Closes the recompute-path
    coverage gap."""
    clone = _clone_with_default(tmp_path, branch="master")
    env = scrub_git_env()
    # Delete the symbolic ref a normal clone sets, simulating a clone that
    # never populated it.
    subprocess.run(
        ["git", "-C", str(clone), "symbolic-ref", "--delete",
         "refs/remotes/origin/HEAD"],
        check=True, env=env, capture_output=True,
    )
    # First read would now fail; default_branch must recompute from the remote.
    assert skill_git.default_branch(clone, env=None) == "master"
