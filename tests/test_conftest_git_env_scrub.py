"""Regression tests for the autouse GIT_* env scrub fixture (#209).

The autouse fixture in tests/conftest.py (_strip_git_env) strips every
GIT_* variable from os.environ before each test. These tests lock that
behavior so a future change cannot silently remove it.

See docs/superpowers/specs/2026-05-22-pytest-git-env-autouse-design.md
for the rationale and the failure mode this closes (PR #206 / issue #209).
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_os_environ_has_no_git_vars() -> None:
    """The autouse fixture must remove all GIT_* keys from os.environ.

    If this fails, either the fixture has been removed from conftest.py
    or it is not running for this test. Either way, the lefthook-leak
    vulnerability is re-opened.
    """
    leaked = sorted(k for k in os.environ if k.startswith("GIT_"))
    assert leaked == [], (
        f"Autouse fixture failed to scrub GIT_* env vars: {leaked}. "
        "See tests/conftest.py and "
        "docs/superpowers/specs/2026-05-22-pytest-git-env-autouse-design.md."
    )


def test_subprocess_inherits_clean_git_env(tmp_path: Path) -> None:
    """A bare subprocess.run(['git', ...]) with no env= must not see
    GIT_* from the parent process.

    This is the lefthook-leak scenario: a parent git invocation (lefthook
    pre-commit, `git rebase -x`, harness wrapper) exports GIT_DIR /
    GIT_INDEX_FILE / GIT_WORK_TREE into the child env. cwd= is silently
    ignored when those vars are set. The autouse fixture closes this by
    cleaning os.environ before each test, so subprocess.run() — which
    inherits os.environ by default when env= is omitted — sees a clean env.
    """
    proc = subprocess.run(
        ["env"], capture_output=True, text=True, check=True,
    )
    leaked = sorted(
        line.split("=", 1)[0]
        for line in proc.stdout.splitlines()
        if line.startswith("GIT_")
    )
    assert leaked == [], (
        f"Subprocess inherited GIT_* env vars from parent: {leaked}. "
        "Tests that shell out to git would write into the parent repo."
    )

    # Belt-and-braces: a real `git` invocation against a fresh repo should
    # succeed without env= and target the path we passed, not the outer repo.
    repo = tmp_path / "scratch"
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "init", "-q", "-b", "main", str(repo)],
        check=True, capture_output=True,
    )
    head_path = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--absolute-git-dir"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert head_path.startswith(str(tmp_path)), (
        f"`git init {repo}` resolved its --absolute-git-dir to "
        f"{head_path!r}, which is outside tmp_path. GIT_DIR is leaking."
    )
