"""End-to-end `skill add` against a fixture monorepo parent."""
import json
import os
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli


FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _clean_git_env() -> dict[str, str]:
    """Strip inherited GIT_* vars so subprocess git calls don't leak into the
    parent repo (see memory: feedback_git_env_leak.md). The pre-commit hook
    runs tests with GIT_DIR/GIT_INDEX_FILE pointing at the calling repo, which
    breaks `git init`/`git commit` inside an unrelated tmp directory.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _make_parent_repo(tmp_path: Path) -> str:
    """Initialise the fixture into a git repo and return its file URL."""
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = _clean_git_env()
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


def test_skill_add_with_skill_flag_installs_subpath(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library

    runner = CliRunner()
    result = runner.invoke(cli, [
        "skill", "add", parent_url, "--skill", "mkdocs",
    ])
    assert result.exit_code == 0, result.output

    canonical = library / "skills" / "mkdocs"
    assert canonical.exists()
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: mkdocs")

    parents_dir = library / "skills" / "_parents"
    parent_clones = list(parents_dir.glob("*/*"))
    assert len(parent_clones) == 1
    assert (parent_clones[0] / "mkdocs" / "SKILL.md").exists()
    assert (parent_clones[0] / "docker" / "SKILL.md").exists()

    lock_path = library / "skills-lock.json"
    raw = json.loads(lock_path.read_text())
    e = raw["skills"]["mkdocs"]
    assert e["skillPath"] == "mkdocs"
    assert e["readOnly"] is True
    assert e["parentUrl"].endswith("/parent-src")


def test_skill_add_with_explicit_subpath(tmp_path, monkeypatch, isolated_library):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()
    result = runner.invoke(cli, [
        "skill", "add", f"{parent_url}/tree/main/docker",
    ])
    assert result.exit_code == 0, result.output
    canonical = library / "skills" / "docker"
    assert (canonical / "SKILL.md").read_text().startswith("---\nname: docker")
    lock = json.loads((library / "skills-lock.json").read_text())
    assert lock["skills"]["docker"]["skillPath"] == "docker"
    assert lock["skills"]["docker"]["readOnly"] is True


def test_skill_add_with_skill_flag_unknown_name_fails(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "skill", "add", parent_url, "--skill", "nonexistent",
    ])
    assert result.exit_code != 0
    assert "nonexistent" in result.output
    assert "mkdocs" in result.output or "docker" in result.output


def test_skill_add_same_parent_twice_reuses_clone(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    library = isolated_library
    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output
    r2 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "docker"])
    assert r2.exit_code == 0, r2.output
    parents = list((library / "skills" / "_parents").glob("*/*"))
    assert len(parents) == 1


def test_skill_add_ambiguous_subpath_and_skill_flag_rejected(
    tmp_path, monkeypatch, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, [
        "skill", "add", f"{parent_url}/tree/main/docker", "--skill", "mkdocs",
    ])
    assert result.exit_code != 0
    assert "ambiguous" in result.output.lower() or "both" in result.output.lower()
