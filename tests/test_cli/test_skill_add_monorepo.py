"""End-to-end `skill add` against a fixture monorepo parent."""
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


def test_skill_add_second_skill_added_after_first_clone(
    tmp_path, monkeypatch, isolated_library,
):
    """#276: adding a skill that was pushed to the monorepo *after* the parent
    cache was first cloned must succeed. The cache is refreshed (fetch + reset)
    before resolving the subpath, so a growing monorepo doesn't fail with
    'SKILL.md not found in parent'."""
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    for cmd in (
        ["git", "init", "-q", "-b", "main"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "init"],
    ):
        subprocess.run(cmd, cwd=parent_src, check=True, env=env)
    parent_url = f"file://{parent_src}"

    runner = CliRunner()
    # First add → clones the parent cache pinned at this commit (mkdocs only-era).
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    # Grow the monorepo: add a brand-new skill dir and commit it.
    new_skill = parent_src / "fresh"
    new_skill.mkdir()
    (new_skill / "SKILL.md").write_text(
        "---\nname: fresh\ndescription: added after first clone\n---\nbody\n"
    )
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "add fresh"],
    ):
        subprocess.run(cmd, cwd=parent_src, check=True, env=env)

    # Second add of the *new* skill must succeed despite the stale cache.
    r2 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "fresh"])
    assert r2.exit_code == 0, r2.output
    assert "not found in parent" not in r2.output
    parents = list((isolated_library / "skills" / "_parents").glob("*/*"))
    assert len(parents) == 1  # same reused cache, now refreshed


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
