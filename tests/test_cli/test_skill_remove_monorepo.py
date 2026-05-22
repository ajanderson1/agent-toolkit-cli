"""Regression tests for `skill remove` against monorepo skills (issue #207).

Monorepo skills install as a symlink in the library, pointing into a shared
parent clone at `<library_root>/_parents/<owner>/<repo>[@<ref>]/`. The remove
path must:

  * `unlink()` the library symlink (not `rmtree`, which refuses symlinks).
  * Sweep the parent clone when no other lock entry still references it.
  * Preserve the parent clone if sibling skills from the same monorepo remain.
"""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli

from tests.conftest import scrub_git_env


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    """Initialise the fixture into a git repo and return its file URL."""
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    subprocess.run(
        ["git", "init", "-q", "-b", "main"],
        cwd=parent_src, check=True, env=env,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "add", "."], cwd=parent_src, check=True, env=env,
    )
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
        cwd=parent_src, check=True, env=env,
    )
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def _add(runner: CliRunner, parent_url: str, skill: str):
    return runner.invoke(cli, ["skill", "add", parent_url, "--skill", skill])


def _parent_clone_dir(library: Path) -> Path:
    """Locate the single `_parents/<owner>/<repo>[@<ref>]/` directory."""
    parents = list((library / "skills" / "_parents").glob("*/*"))
    assert len(parents) == 1, parents
    return parents[0]


def test_remove_monorepo_skill_unlinks_and_sweeps_parent(
    tmp_path, isolated_library,
):
    """Single monorepo skill: remove unlinks symlink and rmtrees parent clone."""
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()

    add_result = _add(runner, parent_url, "mkdocs")
    assert add_result.exit_code == 0, add_result.output

    canonical = library / "skills" / "mkdocs"
    assert canonical.is_symlink()
    parent_clone = _parent_clone_dir(library)

    result = runner.invoke(cli, ["skill", "remove", "mkdocs", "--force"])
    assert result.exit_code == 0, result.output
    # The symlink is gone (no traceback — the original bug).
    assert not canonical.exists()
    assert not canonical.is_symlink()
    # Parent clone swept because no other lock entry references it.
    assert not parent_clone.exists()
    # Lock entry gone.
    lock = json.loads((library / "skills-lock.json").read_text())
    assert "mkdocs" not in lock["skills"]


def test_remove_monorepo_skill_preserves_parent_with_sibling(
    tmp_path, isolated_library,
):
    """Two siblings from same monorepo: removing one keeps the parent clone."""
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()

    assert _add(runner, parent_url, "mkdocs").exit_code == 0
    assert _add(runner, parent_url, "docker").exit_code == 0
    parent_clone = _parent_clone_dir(library)

    result = runner.invoke(cli, ["skill", "remove", "mkdocs", "--force"])
    assert result.exit_code == 0, result.output

    # mkdocs gone, docker still resolvable through the preserved parent.
    assert not (library / "skills" / "mkdocs").exists()
    docker_canonical = library / "skills" / "docker"
    assert docker_canonical.is_symlink()
    assert (docker_canonical / "SKILL.md").exists()

    assert parent_clone.exists()

    lock = json.loads((library / "skills-lock.json").read_text())
    assert "mkdocs" not in lock["skills"]
    assert "docker" in lock["skills"]


def test_remove_last_sibling_sweeps_parent(tmp_path, isolated_library):
    """Removing the final monorepo sibling sweeps the parent clone."""
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()

    assert _add(runner, parent_url, "mkdocs").exit_code == 0
    assert _add(runner, parent_url, "docker").exit_code == 0
    parent_clone = _parent_clone_dir(library)

    assert runner.invoke(
        cli, ["skill", "remove", "mkdocs", "--force"],
    ).exit_code == 0
    assert parent_clone.exists()  # still has docker sibling

    assert runner.invoke(
        cli, ["skill", "remove", "docker", "--force"],
    ).exit_code == 0
    assert not parent_clone.exists()  # last sibling gone, sweep fires
