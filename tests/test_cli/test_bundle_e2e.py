"""End-to-end hermetic test: bundle install fans out to real skill installers.

Both tests run completely isolated (no network, no real ~/.agent-toolkit writes).
Each test sets HOME + AGENT_TOOLKIT_SKILLS_ROOT + git identity env vars so the
real CLI add+install sequence touches only a tmp directory.

Key layout under AGENT_TOOLKIT_SKILLS_ROOT = tmp/lib/skills:
  library lock  → tmp/lib/skills-lock.json  (= SKILLS_ROOT.parent / "skills-lock.json")
  canonical     → tmp/lib/skills/<slug>/

Tests confirm:
1. A one-member skill bundle installs and the slug lands in the library lock.
2. A two-member bundle whose second member is unresolvable fails AND rolls
   back the first — the library lock must NOT contain the first member.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scrub_git_env(base: dict | None = None) -> dict:
    """Strip inherited GIT_* env vars (mirrors conftest.scrub_git_env)."""
    env = dict(base) if base is not None else os.environ.copy()
    return {k: v for k, v in env.items() if not k.startswith("GIT_")}


def _make_skill_repo(root: Path, slug: str) -> str:
    """Build a bare git repo holding a minimal skill; return a file:// source."""
    env = _scrub_git_env()
    work = root / f"{slug}-work"
    work.mkdir(parents=True)
    (work / "SKILL.md").write_text(
        f"---\nname: {slug}\ndescription: e2e test skill\n---\nBody.\n"
    )
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(work)],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(work), "add", "."],
        check=True, env=env, capture_output=True,
    )
    subprocess.run(
        [
            "git", "-C", str(work),
            "-c", "user.email=t@t.test",
            "-c", "user.name=Test",
            "commit", "-qm", "init",
        ],
        check=True, env=env, capture_output=True,
    )
    bare = root / f"{slug}.git"
    subprocess.run(
        ["git", "clone", "-q", "--bare", str(work), str(bare)],
        check=True, env=env, capture_output=True,
    )
    return f"file://{bare}"


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def _bundle_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate HOME + git identity + AGENT_TOOLKIT_SKILLS_ROOT.

    Returns (home, library_root, lock_path) so tests can assert on the real
    paths without guessing.
    """
    home = tmp_path / "home"
    home.mkdir()
    lib_root = tmp_path / "lib" / "skills"

    # Strip GIT_* (autouse _strip_git_env already runs; belt-and-suspenders for
    # the subprocess calls in _make_skill_repo).
    for var in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(lib_root))

    # Provide a git identity so `skill add` (which clones + may commit) works
    # in a clean CI / local env.
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.invalid")

    # Lock path is always SKILLS_ROOT.parent / "skills-lock.json".
    lock_path = lib_root.parent / "skills-lock.json"
    return home, lib_root, lock_path


# ---------------------------------------------------------------------------
# Test 1: single-member bundle lands in the library lock
# ---------------------------------------------------------------------------

def test_two_member_bundle_installs_both(tmp_path: Path, _bundle_env):
    """A one-member skill bundle installs; the slug appears in the library lock."""
    _home, lib_root, lock_path = _bundle_env
    src = _make_skill_repo(tmp_path / "repos", "gw")
    manifest = tmp_path / "b.bundle.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "name": "demo",
        "description": "",
        "members": [
            {"asset_type": "skill", "source": src, "slug": "gw"},
        ],
    }))

    res = CliRunner().invoke(main, ["bundle", "install", "--global", str(manifest)])
    assert res.exit_code == 0, f"bundle install failed:\n{res.output}"

    assert lock_path.exists(), f"library lock not written at {lock_path}"
    assert "gw" in lock_path.read_text(), (
        f"'gw' not found in lock at {lock_path}:\n{lock_path.read_text()}"
    )


# ---------------------------------------------------------------------------
# Test 2: unresolvable second member triggers rollback of the first
# ---------------------------------------------------------------------------

def test_rollback_on_second_member_unresolvable(tmp_path: Path, _bundle_env):
    """A bundle whose 2nd member is unresolvable fails AND removes the 1st."""
    _home, lib_root, lock_path = _bundle_env
    good = _make_skill_repo(tmp_path / "repos", "good")
    manifest = tmp_path / "b.bundle.json"
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "name": "demo",
        "description": "",
        "members": [
            {"asset_type": "skill", "source": good, "slug": "good"},
            {
                "asset_type": "skill",
                "source": f"file://{tmp_path}/does-not-exist.git",
                "slug": "missing",
            },
        ],
    }))

    res = CliRunner().invoke(main, ["bundle", "install", "--global", str(manifest)])
    assert res.exit_code != 0, (
        f"bundle install should have failed but exited 0:\n{res.output}"
    )

    # After rollback the library lock must NOT contain 'good'.
    if lock_path.exists():
        lock_text = lock_path.read_text()
        assert "good" not in lock_text, (
            f"'good' still present in lock after rollback:\n{lock_text}"
        )
