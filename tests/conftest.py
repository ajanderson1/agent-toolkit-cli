"""Shared fixtures across the test suite."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from click.testing import CliRunner
from agent_toolkit_cli.cli import main


@dataclass
class GitSandbox:
    upstream: Path     # bare repo acting as the "remote"
    clone: Path        # working clone of upstream, pre-populated
    env: dict[str, str]


def scrub_git_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Strip inherited GIT_* env vars. See memory feedback_git_env_leak.md."""
    env = dict(base) if base is not None else os.environ.copy()
    return {k: v for k, v in env.items() if not k.startswith("GIT_")}


@pytest.fixture(autouse=True)
def _strip_git_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip inherited GIT_* env vars from os.environ for every test.

    Closes #209 — prevents the lefthook-leak trap: a test that shells out
    to git without an explicit env= argument no longer inherits GIT_DIR /
    GIT_INDEX_FILE from a parent hook and cannot accidentally write
    commits into the outer repo. monkeypatch restores env at teardown.
    """
    # Snapshot keys before mutating — iterating os.environ while
    # deleting from it would be undefined behaviour.
    for var in [k for k in os.environ if k.startswith("GIT_")]:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def git_sandbox(tmp_path: Path) -> GitSandbox:
    # Belt-and-braces: autouse _strip_git_env has already cleared GIT_*
    # from os.environ; this explicit scrub keeps the fixture self-contained
    # and self-documenting even if the autouse layer ever moves.
    env = scrub_git_env()
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


def _git(sandbox, *args):
    subprocess.run(["git", "-C", str(sandbox.clone), *args],
                   check=True, env=sandbox.env, capture_output=True)


def _advance_remote(sandbox, name="UPSTREAM.md", body="upstream\n"):
    """Push one commit to upstream via a throwaway clone."""
    helper = sandbox.upstream.parent / "remote-advance-helper"
    # Clone once per git_sandbox lifetime (one call per fixture is the contract).
    if not helper.exists():
        subprocess.run(["git", "clone", str(sandbox.upstream), str(helper)],
                       check=True, env=sandbox.env, capture_output=True)
    (helper / name).write_text(body)
    subprocess.run(["git", "-C", str(helper), "add", "-A"],
                   check=True, env=sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "commit", "-m", "upstream"],
                   check=True, env=sandbox.env, capture_output=True)
    subprocess.run(["git", "-C", str(helper), "push", "origin", "main"],
                   check=True, env=sandbox.env, capture_output=True)


@pytest.fixture
def make_behind(git_sandbox) -> GitSandbox:
    """Upstream advanced; clone left behind (not fetched)."""
    _advance_remote(git_sandbox)
    return git_sandbox


@pytest.fixture
def make_ahead(git_sandbox) -> GitSandbox:
    """Clone has a local commit not pushed to upstream."""
    (git_sandbox.clone / "LOCAL.md").write_text("local\n")
    _git(git_sandbox, "add", "-A")
    _git(git_sandbox, "commit", "-m", "local")
    return git_sandbox


@pytest.fixture
def make_diverged(git_sandbox) -> GitSandbox:
    """Both sides committed on non-conflicting paths."""
    (git_sandbox.clone / "LOCAL.md").write_text("local\n")
    _git(git_sandbox, "add", "-A")
    _git(git_sandbox, "commit", "-m", "local")
    _advance_remote(git_sandbox)
    return git_sandbox


@pytest.fixture
def make_conflict(git_sandbox) -> GitSandbox:
    """Both sides edited the same line of SKILL.md."""
    (git_sandbox.clone / "SKILL.md").write_text("local edit\n")
    _git(git_sandbox, "add", "-A")
    _git(git_sandbox, "commit", "-m", "local SKILL edit")
    _advance_remote(git_sandbox, name="SKILL.md", body="upstream edit\n")
    return git_sandbox


@pytest.fixture
def make_dirty(git_sandbox) -> GitSandbox:
    """Uncommitted working-tree change."""
    (git_sandbox.clone / "SKILL.md").write_text("uncommitted edit\n")
    return git_sandbox


# ---------------------------------------------------------------------------
# Install-shaped fixtures (Task 3)
# ---------------------------------------------------------------------------

@dataclass
class InstalledSkill:
    slug: str
    canonical: Path
    lock_path: Path
    lock_text: str
    read_only: bool


@pytest.fixture
def _cli_env(git_sandbox, tmp_path, monkeypatch):
    """Monkeypatch env so the real CLI installs into a sandbox library root.

    library_lock_path() = library_root().parent / "skills-lock.json", so for
    AGENT_TOOLKIT_SKILLS_ROOT = tmp_path/lib/skills the lock lands at
    tmp_path/lib/skills-lock.json (one level above the skills dir).
    """
    root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(root))
    return root


@pytest.fixture
def installed_skill(git_sandbox, _cli_env) -> InstalledSkill:
    """A git-managed global skill added via the real CLI."""
    root = _cli_env
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream),
                             "--slug", "demo"])
    assert r.exit_code == 0, r.output
    canonical = root / "demo"
    # Lock lives at library_root().parent / "skills-lock.json"
    lock_path = root.parent / "skills-lock.json"
    return InstalledSkill(
        slug="demo", canonical=canonical, lock_path=lock_path,
        lock_text=lock_path.read_text(), read_only=False,
    )


@pytest.fixture
def copymode_skill(_cli_env) -> InstalledSkill:
    """A canonical with plain files and no .git/ (copy-mode)."""
    root = _cli_env
    canonical = root / "copydemo"
    canonical.mkdir(parents=True)
    (canonical / "SKILL.md").write_text(
        "---\nname: copydemo\ndescription: copy.\n---\n# copydemo\n"
    )
    # Lock lives at library_root().parent / "skills-lock.json"
    lock_path = root.parent / "skills-lock.json"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text('{"version": 1, "skills": {"copydemo": {}}}')
    return InstalledSkill(
        slug="copydemo", canonical=canonical, lock_path=lock_path,
        lock_text=lock_path.read_text(), read_only=False,
    )


@pytest.fixture
def monorepo_skill(tmp_path, monkeypatch) -> InstalledSkill:
    """A read-only monorepo skill added via the real CLI."""
    from tests.test_cli.test_skill_update_monorepo import _init_parent
    parent = _init_parent(tmp_path)
    root = tmp_path / "library" / "skills"
    # GIT_* scrubbing handled by autouse _strip_git_env; _init_parent uses inline -c for identity.
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(root))
    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", f"file://{parent}",
                             "--skill", "mkdocs"])
    assert r.exit_code == 0, r.output
    # Lock lives at library_root().parent / "skills-lock.json"
    lock_path = root.parent / "skills-lock.json"
    return InstalledSkill(
        slug="mkdocs", canonical=root / "mkdocs", lock_path=lock_path,
        lock_text=lock_path.read_text(), read_only=True,
    )
