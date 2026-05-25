"""Relocated project canonical: external store + uniform projection symlinks."""
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli import skill_install
from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_lock import LockEntry, add_entry, read_lock, write_lock
from agent_toolkit_cli.skill_paths import (
    canonical_skill_dir, library_lock_path, project_store_root,
)

from tests.conftest import scrub_git_env

FIXTURE = Path(__file__).parent.parent / "fixtures" / "monorepo_skills"


def _make_parent_repo(tmp_path: Path) -> str:
    parent_src = tmp_path / "parent-src"
    subprocess.run(["cp", "-R", str(FIXTURE), str(parent_src)], check=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
                   cwd=parent_src, check=True, env=env)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-q", "-m", "init"], cwd=parent_src, check=True, env=env)
    return f"file://{parent_src}"


@pytest.fixture
def isolated_library(tmp_path, monkeypatch):
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    return library


def _seed_global_monorepo_entry(parent_url: str, slug: str, subpath: str) -> None:
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source="vercel-labs/agent-browser", source_type="github", ref=None,
        skill_path=subpath, upstream_sha=None, local_sha=None,
        parent_url=parent_url, read_only=True,
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def test_project_universal_gets_symlink_into_external_store(
    tmp_path, isolated_library, monkeypatch,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.chdir(project)

    runner = CliRunner(env=scrub_git_env())
    result = runner.invoke(cli, ["skill", "install", "mkdocs",
                                 "--agents", "claude-code", "-p"])
    assert result.exit_code == 0, result.output

    canonical = canonical_skill_dir("mkdocs", scope="project", project=project)
    assert canonical == project_store_root(project) / "mkdocs"
    assert (canonical / "SKILL.md").exists()

    uni = project / ".agents" / "skills" / "mkdocs"
    assert uni.is_symlink(), "project-universal must now get a projection symlink"
    assert (uni / "SKILL.md").exists()

    assert not (project / ".agents" / "skills" / "_parents").exists()


def test_ensure_project_canonical_writes_to_external_store(
    tmp_path, isolated_library,
):
    parent_url = _make_parent_repo(tmp_path)
    _seed_global_monorepo_entry(parent_url, "mkdocs", "mkdocs")
    project = tmp_path / "proj"
    project.mkdir()

    canonical = skill_install.ensure_project_canonical(
        slug="mkdocs", project=project,
        global_lock_path=library_lock_path(), env=scrub_git_env(),
    )
    assert canonical == project_store_root(project) / "mkdocs"
    assert canonical.is_symlink()  # monorepo → symlink into store _parents
    assert (canonical / "SKILL.md").exists()
    assert (project_store_root(project) / "_parents").exists()
    assert not (project / ".agents" / "skills" / "_parents").exists()
    e = json.loads((project / "skills-lock.json").read_text())["skills"]["mkdocs"]
    assert e["parentUrl"].endswith("/parent-src")
